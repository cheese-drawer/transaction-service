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
import db_wrapper as db

# internal dependencies
from .start_server import Runner

# application logic
from .models import Transaction, TransactionData
# import transaction

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
    Build a Pattern using JSONEncoder Extension.

    Intended to be passed to an AMQP Worker on initialization to replace
    default Pattern with default JSONEncoder.
    """
    pattern = cast(
        JSONGzipRPC,
        await JSONGzipRPC.create(channel))
    # replace default encoder with extended JSON encoder
    pattern.json_encoder = ExtendedJSONEncoder()

    return pattern

# get connection parameters from env, or use defaults
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
# service_to_service = worker.QueueWorker(broker_connection_params)


#
# MODELS
#

transaction_model = Transaction(database)


#
# WORKER ROUTES
#

@response_and_request.route('transaction.get')
async def get(data: Optional[Dict[str, Any]]) -> List[TransactionData]:
    """Get list of Transactions."""
    LOGGER.info(f'data: {data}')

    if data is None:
        return await transaction_model.read.all()

    if data.get('id') is not None:
        return [await transaction_model.read.one_by_id(data['id'])]

    return await transaction_model.read.all(
        count=data.get('count'),
        offset=data.get('offset'))

#
# RUN SERVICE
#

runner = Runner()

runner.register_database(database)
runner.register_worker(response_and_request)
# runner.register_worker(service_to_service)

runner.run()
