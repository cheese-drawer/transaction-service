"""API configuration & definition for Transaction Service"""

# standard library imports
import logging
import os
from typing import Any, Hashable, Optional, List, Dict

# third party imports
import amqp_worker as worker
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

# get connection parameters from dotenv, or use defaults
broker_connection_params = worker.ConnectionParameters(
    host=os.getenv('BROKER_HOST', 'localhost'),
    port=int(os.getenv('BROKER_PORT', '5672')),
    user=os.getenv('BROKER_USER', 'guest'),
    password=os.getenv('BROKER_PASS', 'guest'))

# initialize Worker & assign to global variable
response_and_request = worker.RPCWorker(broker_connection_params)
# service_to_service = worker.QueueWorker(broker_connection_params)


#
# MODELS
#

transaction_model = Transaction(database)


#
# WORKER ROUTES
#

@response_and_request.route('transaction.get')
async def get(data: Optional[Dict[Hashable, Any]]) -> List[TransactionData]:
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
