"""API configuration & definition for Transaction Service."""

# standard library imports
from datetime import date
from decimal import Decimal
import logging
import os
from typing import (
    cast,
    Any,
    Optional,
    List,
    Dict
)
from uuid import UUID

# third party imports
from amqp_worker.connection import ConnectionParameters, Channel
from amqp_worker.serializer import ResponseEncoder, JSONEncoderTypes
from amqp_worker.rpc_worker import RPCWorker, JSONGzipRPC
from amqp_worker.queue_worker import QueueWorker, JSONGzipMaster
import db_wrapper as db
# pylint thinks BaseModel doesn't exist in pydantic
# ignoring it since MyPy's able to parse it
# and validates that BaseModel exists
from pydantic import (  # pylint: disable=no-name-in-module
    BaseModel, ValidationError)

# internal dependencies
from .start_server import Runner

# application logic
from .models import Transaction, TransactionData

#
# ENVIRONMENT
#


def get_mode() -> str:
    """Determine if running application in 'production' or 'development'.

    Uses `MODE` environment variable & falls back to 'development' if no
    variable exists. Requires mode to be set to either 'development' OR
    'production', raises an error if anything else is specified.
    """
    env = os.getenv('MODE', 'development')  # default to 'development'

    if env in ('development', 'production'):
        return env

    raise TypeError(
        'MODE must be either `production`, `development`, or unset '
        '(defaults to `development`)')


MODE = get_mode()


#
# LOGGING
#

LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO
    if MODE == 'development'
    else logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


#
# WORKER SETUP
#

# This worker needs to be able to parse pydantic BaseModels & some
# sub-types as JSON. Extending amqp_worker's ResponseEncoder (itself an
# extension of JSONEncoder) & building an amqp pattern object that uses
# our extended encoder allows amqp_worker to serialize our Models
# correctly.

class ExtendedJSONEncoder(ResponseEncoder):
    """Extend JSONEncoder to handle additional data types.

    Now handles the following new types:

    -------------------------------
    | python             | json   |
    |--------------------|--------|
    | pydantic.ModelBase | object | -> to dict, then to JSON object
    | datetime.date      | string | -> to isoformat str, then to JSON string
    | uuid.UUID          | string | -> to str, then to JSON string
    | decimal.Decimal    | number | -> to float, then to JSON number
    -------------------------------

    All others fall back to default JSONEncoder rules.
    """

    def default(self, o: Any) -> JSONEncoderTypes:
        """
        Add serialization for new types.

        Adds support for pydantic.BaseModel, datetime.date, uuid.UUID, &
        decimal.Decimal.
        """
        LOGGER.debug('Using custom serializer...')
        LOGGER.debug(f'o: {o}')
        LOGGER.debug(f'type: {type(o)}')

        # first parse for extended types:

        if isinstance(o, BaseModel):
            LOGGER.debug('o is instance of BaseModel')
            return o.dict()

        if isinstance(o, date):
            LOGGER.debug('o is instance of date')
            return o.isoformat()

        if isinstance(o, UUID):
            LOGGER.debug('o is instance of UUID')
            return str(o)

        if isinstance(o, Decimal):
            LOGGER.debug('o is instance of UUID')
            return float(o)

        # then, fall back to ResponseEncoder.default method
        return ResponseEncoder.default(self, o)


async def json_gzip_rpc_factory(
    channel: Channel
) -> JSONGzipRPC:
    """
    Build a RPC Pattern using JSONEncoder Extension.

    Intended to be passed to a RPCWorker on initialization to replace
    default Pattern with default JSONEncoder.
    """
    pattern = cast(
        JSONGzipRPC,
        await JSONGzipRPC.create(channel))
    # replace default encoder with extended JSON encoder
    pattern.json_encoder = ExtendedJSONEncoder()

    return pattern


def json_gzip_queue_factory(
    channel: Channel
) -> JSONGzipMaster:
    """
    Build a Master Pattern using JSONEncoder Extension.

    Intended to be passed to a QueueWorker on initialization to replace
    default Pattern with default JSONEncoder.
    """
    pattern = JSONGzipMaster(channel)
    # replace default encoder with extended JSON encoder
    pattern.json_encoder = ExtendedJSONEncoder()

    return pattern


# get connection parameters from dotenv, or use defaults
broker_connection_params = ConnectionParameters(
    host=os.getenv('BROKER_HOST', 'localhost'),
    port=int(os.getenv('BROKER_PORT', '5672')),
    user=os.getenv('BROKER_USER', 'guest'),
    password=os.getenv('BROKER_PASS', 'guest'))

# initialize Worker with connection parameters & factory function to build
# pattern with custom JSONEncoder created above & assign to global
# variable
response_and_request = RPCWorker(
    broker_connection_params,
    pattern_factory=json_gzip_rpc_factory)
service_to_service = QueueWorker(
    broker_connection_params,
    pattern_factory=json_gzip_queue_factory)


#
# DATABASE SETUP
#

db_connection_params = db.ConnectionParameters(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASS', 'postgres'),
    database=os.getenv('DB_NAME', 'postgres'))

# init db & connect
database = db.Client(db_connection_params)


#
# DATABASE MODELS
#

transaction_model = Transaction(database)


#
# WORKER ROUTES
#

# Defining expected props as a BaseModel leverages pydantic's runtime type
# validation on data received by route
class TransactionGetProps(BaseModel):
    """Interface for `data` argument on `transaction.get` route."""

    # BaseModel is essentially a dataclass, no public methods needed
    # pylint: disable=too-few-public-methods

    id: Optional[UUID]
    count: Optional[int]
    offset: Optional[int]


@response_and_request.route('transaction.get')
async def get(data: Optional[Dict[str, Any]]) -> List[TransactionData]:
    """Get list of Transactions."""
    LOGGER.info(f'Request received on `transaction.get` with data: {data}')

    if data is not None:
        # validate received data by initializing as Props Model
        try:
            props = TransactionGetProps(**data)
        except ValidationError as err:
            raise Exception('Required key missing on JSON Request.') from err

        # when a Transaction ID is given, ignore all other data & get that one
        # specific Transaction from the database
        if props.id is not None:
            return [await transaction_model.read.one_by_id(str(props.id))]

        # otherwise return a list of transactions, passing any value to count &
        # offset to optionally customize pagination
        return await transaction_model.read.many(
            count=props.count,
            offset=props.offset)

    # props don't have to be given; defaults to getting the first page of
    # Transactions when no data is received
    return await transaction_model.read.many()


class TransactionUpdateProps(BaseModel):
    """Interface for `data` argument on `transaction.update` route."""

    # BaseModel is essentially a dataclass, no public methods needed
    # pylint: disable=too-few-public-methods

    transaction_id: UUID
    changes: Dict[str, Any]


@response_and_request.route('transaction.update')
async def update(data: Dict[str, Any]) -> List[TransactionData]:
    """Update given Transaction."""
    LOGGER.info(f'Request received on `transaction.update` with data: {data}')

    # validate received data by initializing as Props Model
    try:
        props = TransactionUpdateProps(**data)
    except ValidationError as err:
        raise Exception('Required key missing on JSON Request.') from err

    return [await transaction_model.update.one_by_id(
        str(props.transaction_id),
        props.changes)]


class TransactionNewProps(BaseModel):
    """Interface for `data` argument on `transaction.s2s.new` route."""

    # BaseModel is essentially a dataclass, no public methods needed
    # pylint: disable=too-few-public-methods

    transactions: List[TransactionData]


@service_to_service.route('transaction.s2s.new')
async def new(data: Dict[str, Any]) -> None:
    """Add given transactions to the database."""
    LOGGER.info(f'Request received on `transaction.s2s.new` with data: {data}')

    # validate received data as TransactionData
    try:
        props = TransactionNewProps(**data)
    except ValidationError as err:
        raise Exception('Given data is invalid.') from err

    await transaction_model.create.many(props.transactions)

#
# RUN SERVICE
#

runner = Runner()

runner.register_database(database)
runner.register_worker(response_and_request)
runner.register_worker(service_to_service)

runner.run()
