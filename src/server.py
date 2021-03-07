"""A simple example of implementing a Service's APIs.

Uses a declarative API based on decorators, similar to Flask to declare API
'routes'.  These routes are really callback functions assigned to a queue
(named in the decorator argument) that executes any time a message (given
as the data keyword argument to the callback) is received on that queue.

For the Response & Request API, a handler returns a value that is then sent as
the response directly to the message originator (this is done with an
RPCWorker from the amqp_worker library). The Service to Service API uses a
QueueWorker & it's route handlers don't return a value because no response is
sent for any requests received.

This example also implements a simple database interface to a Postgres server,
using aiopg. To simplify the API definition, the db interface is wrapped in a
simplified API that handles connecting to the server, exposing an `execute`
method for executing SQL queries, & disconnecting to the server. Additionally,
the database abstraction exposes a Model concept to encapsulate database query
logic & type management as a separate concern from worker routing & route
handling.

The service API runs asynchronously, allowing it to handle multiple requests
simultaneously & not block on a particularly long-running handler or database
request. This requires running the database client & AMQP workers in an
asynchronous event loop, handled here by the `register_database`,
`register_worker`, & `run` methods from `start_server`.
"""

# standard library imports
import logging
import os
from typing import Any, List, Dict, TypedDict

# third party imports
import amqp_worker as worker
import db_wrapper as db

# internal dependencies
from start_server import Runner

# application logic
from models import ExampleItem, ExampleItemData, SimpleData
import lib

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
# NOTE: use this one for debugging, very verbose output
# logging.basicConfig(level=logging.DEBUG)
# NOTE: or use this one for production or development
# sets development logging based on MODE
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
service_to_service = worker.QueueWorker(broker_connection_params)


#
# MODELS
#

# NOTE: Models are simply an organizational tool for grouping a schema &
# related queries. A Model is initialized by giving it a ModelData object as
# a Type variable, in addition to a database client object & a table name.
# An built Model will include a few built-in CRUD queries (create one,
# read one by id, update one by id, & delete one by id).

# NOTE: Using a Model is entirely unnecessary, but it will help with
# separation of concerns, making it easier to decouple your application
# logic from your database schema & queries.

# If you don't need any queries beyond the built-in ones, you can simply
# build a model from only a ModelData definition, database Client object, &
# table name
simple_model = db.Model[SimpleData](database, 'simple')

# Otherwise, it's best to extend the model object with additional queries
# in another file, then initialize it here
example_model = ExampleItem(database)


#
# WORKER ROUTES
#

# NOTE: use route decorator on RPCWorker instance similar to defining a
# route in Flask, but using asynchronous functions as handlers instead
# of standard synchronous functions

# NOTE: This is the section that you'll change the most; it's possible that
# you won't need to change anything else in many scenarios (I think)


# NOTE: define a route using the @response_and_request.route decorator
# provided by RPCWorker
@response_and_request.route('test')
async def test(data: str) -> str:
    """Contrived example of an long running handler.

    Uses async/await to allow other tasks to be handled while
    this one runs.
    """
    # Awaiting methods that may take a long time is best practice. This allows
    # the worker to handle other requests while waiting on this one to be
    # ready.
    processed = await lib.do_a_long_thing()
    result = f'{data} {processed}'
    LOGGER.info(result)  # print result when processed
    # tasks must return an object capable of being JSON serialized
    # the result is sent as JSON reply to the task originator
    return result


@response_and_request.route('will-error')
async def will_error(data: str) -> str:
    """Simplified example of a handler that raises an Exception."""
    an_int = lib.do_a_quick_thing()

    raise Exception(f'Just an exception: {an_int}, {data}')


@response_and_request.route('dictionary')
async def dictionary(data: Dict[str, Any]) -> Dict[str, Any]:
    """Alternative example that works with a Dict instead of a string."""
    return {
        **data,
        'bar': 'baz'
    }


@response_and_request.route('db')
async def db_route(_: Any) -> List[Any]:
    """Simplified example of a handler that directly queries the database."""
    # PENDS python 3.9 support in pylint
    # pylint: disable=inherit-non-class
    # pylint: disable=too-few-public-methods
    # NOTE: db_wrapper uses psycopg2's RealDictCursor under the hood, so query
    # results will be returned in the form of a list of dictionaries, one for
    # each result. In this case, the result will be a list of dictionaries,
    # each with only one field, `table_name`, & a value type of `str`.
    class TableName(TypedDict):
        """DB query result shape for querying table names."""

        table_name: str

    tables_dicts: List[TableName] = await database.execute_and_return(
        "SELECT table_name "
        "FROM information_schema.tables "
        "WHERE table_schema = 'public';")

    tables: List[str] = [table['table_name'] for table in tables_dicts]

    return tables


@response_and_request.route('example-items')
async def model_route(query: str) -> List[ExampleItemData]:
    """Implement example handler that uses Model to interact with database."""
    # psycopg2's sql composition module (used to query built in
    # ExampleItemModel) interpolates a None value as an empty string. This
    # means a missing query string in this route will result in a query
    # matching no records, & send a response of an empty array, when instead
    # the user should be alerted that they forgot a query string in their
    # message.
    if query is None:
        raise Exception(
            'No Message: no message body was sent when one is required.')

    return await example_model.read.all_by_string(query)


@service_to_service.route('queue-test')
async def queue_test(data: str) -> None:
    """Simplified example of a queue consumer handler.

    Unlike RPC routes, Queue routes do not need to return anything as no
    response is sent. Instead, they simply perform some work usually using
    the given data. This example simply logs the data.
    """
    LOGGER.info(f'Task received in queue_test: {data}')


#
# RUN SERVICE
#

runner = Runner()

# Add database client to Runner's objects that need run inside asyncio
# event loop
runner.register_database(database)
# NOTE: you can theoretically run multiple database clients (maybe you
# need different parts of your application to talk to different databases
# for some reason), but you likely won't need to

# Adds response_and_request to list of workers to be run when application
# is executed
runner.register_worker(response_and_request)
# NOTE: Registering the worker here like this allows for registering multiple
# workers. This means the same application can have an RPCWorker as well
# as any other Worker intended for a different AMQP Pattern (i.e. work
# queues or fanout)
# Adding an additional worker just requires initializing an instance of it
# above, then passing that instance (after adding any routes or other
# config) to another call to `register_worker()`, as seen here, where we
# register the queue worker as well
runner.register_worker(service_to_service)

# Run all registered workers & database client
# NOTE: using run like this encapsulates all the asyncio event loop
# management to run all of the workers passed to `register_worker()`
# simultaneously & asynchronously without having to clutter up the code
# here for the application API
runner.run()
