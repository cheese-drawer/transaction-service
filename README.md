# Python microservice seed project

The following seed project can be used to set up a python-based service to run in Docker, communicating over AMQP via RabbitMQ (using [cheese-drawer/lib-python-amqp-worker](https://github.com/cheese-drawer/lib-python-amqp-worker)) and storing data in PostgreSQL (using [cheese-drawer/lib-python-db-wrapper](https://github.com/cheese-drawer/lib-python-db-wrapper)).
The project structure places Docker configurations at the root (along with dev tool configs, like mypy, pylint, etc.), the application source at `./src`, & tests at `./test`:

```
.
├── Dockerfile                  # Dockerfile to build this service
├── dev.docker-compose.yml      # Development & test stack composition
│                               #   (includes rabbitmq & postgres services)
├── manage.py                   # Database management script, handles migrations
├── migrations/...              # Sql scripts for migrations live here
├── rabbitmq-configs/...        # Configuration for dev stack rabbitmq service,
│                               #   you shouldn't need to touch this
├── requirements
│   ├── dev.txt                 # Development only requirements
│   ├── prod.txt                # Production only requirements
│   └── test_e2e.txt            # Integration testing only requirements
├── requirements.txt            # Defers to requirements/prod.txt
├── scripts/...                 # Helper scripts to simplify running tests,
│                               #   typechecking, linting, starting the dev stack,
│                               #   and more
├── src                         # Application source lives here, this is the main
│   │                           #   area where you'll be changing things
│   ├── lib.py                  # An example of separating service route logic
│   │                           #   from application business logic
│   ├── models/...              # Data models are defined here, see
│   │                           #   cheese-drawer/lib-python-db-wrapper for more
│   ├── server.py               # Service workers, routes, & database connections
│   │                           #   are defined here
│   └── start_server.py         # Module to orchestrate the amqp workers &
│                               #   database connections in an asyncio event loop,
│                               #   you shouldn't need to touch this
├── stubs/...                   # Mypy stubs for untyped modules, you probably
│                               #   won't need to change this
└── test                        # Tests go here
```

## Prerequisites

This seed assumes you have the following installed:

1. Docker
2. Docker Compose (if you have Docker, you likely have docker-compose as well)
3. *Optional:* Event Notify Test Runner (eradman/entr)

### Docker

Get Docker for your local machine by [going here](https://docs.docker.com/get-docker/) & following the instructions for your OS/desired setup.

### Docker Compose

[According to Docker](https://docs.docker.com/compose/install/), if you have Docker Desktop, you already have Docker Compose. If you're on Linux or don't have Docker Desktop on your machine, you may need to install Docker Compose manually. See [the installation instructions](https://docs.docker.com/compose/install/) for more.

### Event Notify Test Runner

This dependency is only needed if you want to use the provided development script (`./scripts/dev`) to handle starting up a dev stack, then watching your application source for changes & restarting your application in the stack on change automatically.
To install it, refer to [eradman/entr](https://github.com/eradman/entr) on GitHub.


## Installation

To use this to seed a new project, just download & unpack a release, install all the dependencies with `pip install -r requirements/prod.txt -r requirements/dev.txt -r requirements/test_e2e.txt`, then start modifying as needed.
Alternatively, clone this repo to your local machine, then delete the `.git/` directory and init a new repo with `git init`.

##  Development Usage

The easiest way to run the service is using the included script at `./scripts/dev` to start up a dev stack with the service included.
To tear down the stack, just hit CTRL+C.

If you don't have eradman/entr installed, then `./scripts/dev` won't work.
Instead, you'll need to manually start the stack by running `docker-compose -f dev.docker-compose.yml up`.
Then you can make changes to your local `./src` directory, running `docker-compose -f dev.docker-compose.yml restart app` when you want to see your changes take effect in the running stack.
Finally, you can test down the stack using `docker-compose -f dev.docker-compose.yml down`.

The core of the project is defining your application under `./src`.
This seed is built with a few assumptions about your application:

- You are using [cheese-drawer/lib-python-amqp-worker](https://github.com/cheese-drawer/lib-python-amqp-worker)) to manage your AMQP layer
- You are using [cheese-drawer/lib-python-db-wrapper](https://github.com/cheese-drawer/lib-python-db-wrapper) to manage your database layer

While you should read more about each of these libraries to see how to use them properly, the basic idea is simple.
In `./src/server.py`, you'll define the connections to your AMQP broker & your PostgreSQL server (you should be using environment variables passed to the Docker container for most of this), then define AMQP Worker routes with `amqp_worker.RPCWorker.route` or `amqp_worker.QueueWorker.route`, a database Client with `db_wrapper.Client`, & data Models with `db_wrapper.Model` & `db_wrapper.ModelData` to define the Model's types. At the end, you'll need to initialize the Workers & Database Client in an `asyncio` event loop.
An abbreviated example is defined below:

```python
# ./src/server.py

#
# DEPENDENCIES
#

# third party libraries
import amqp_worker as worker
import db_wrapper as db

# internal dependencies
from start_server import Runner

# application logic
from models import ExampleItem, ExampleItemData, SimpleData

#
# DATABASE SETUP
#

db_connection_params = db.ConnectionParameters(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASS', 'postgres'),
    database=os.getenv('DB_NAME', 'postgres'))

# init database Client & connect
database = db.Client(db_connection_params)

#
# AMQP WORKER SETUP
#

# get connection parameters from dotenv, or use defaults
broker_connection_params = worker.ConnectionParameters(
    host=os.getenv('BROKER_HOST', 'localhost'),
    port=int(os.getenv('BROKER_PORT', '5672')),
    user=os.getenv('BROKER_USER', 'guest'),
    password=os.getenv('BROKER_PASS', 'guest'))

# initialize Worker
response_and_request = worker.RPCWorker(broker_connection_params)

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
# NOTE: define a route using the @response_and_request.route decorator
# provided by RPCWorker
@response_and_request.route('hello_world')
async def hello_world(data: str) -> str:
    """Simplified example of an AMQP Worker handler.

    Uses async/await to allow other tasks to be handled while
    this one runs. Although this example doesn't require async/await
    for performance, the Worker requires the handler be defined as
    asynchronous anyways.
    """
    return 'Hello world!'

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
# config) to another call to `register_worker()`

# Run all registered workers
# NOTE: using run like this encapsulates all the asyncio event loop
# management to run all of the workers passed to `register_worker()`
# simultaneously & asynchronously without having to clutter up the code
# here for the application API
runner.run()
```

The above example is pulled nearly verbatim from the source at `./src/server.py`.
The source in this seed project includes copious comments inline to help explain how to use each part.
See `./src/server.py` & `./src/models/*` for more details.

### Helper scripts

This seed project comes with a few helper scripts already set up at `./scripts`.
These can be used to perform a variety of development tasks, including starting up the development stack, [as seen above](#development-usage).

Available scripts:

- auto formatting per PEP8: `./scripts/autofix`
- linting: `./scripts/lint`
- type checking with mypy: `./scripts/typecheck`
- start up a dev stack: `./scripts/dev`
- running tests (unit & integration): `./scripts/test`
- build a new image of this service: `./scripts/build`
- manage database migrations: `./scripts/manage`

Additionally, there's a script included to orchestrate calling of the other scripts, `./scripts/pj`. This script is intended to be symlinked on your path, so you can simplify calling any of the scripts by typing `pj <script name>` instead of `<path to root>/scripts/<script name>`.

Some of the scripts are very straightforward, deferring to their respective tools to do a job & report the results:

- `autofix` uses autopep8
- `lint` uses pylint, pycodestyle, & pydocstyle
- `typecheck` uses mypy
- `build` calls Docker Compose's build command

`test`, `dev`, & `manage` are a little more complex & their behaviour is covered below.

#### `dev` script

Used to start up a dev stack, restart the service on source changes, follow the log input, & tear down the stack when done.

This script uses Docker Compose under the hood to spin up the dev stack defined at dev.docker-compose.yml (Rabbitmq broker, PostgreSQL, & this service--named `app`).
The starting  docker-compose file  mounts your application source at `./src` as a volume on your running service, making it easier to make changes in the running service.
Additionally, this script uses eradman/entr to watch `./src` for changes & restarts the app service on change.
After starting the stack & setting up the watcher, the script follows log output from the running stack.

Because the script is just Docker Compose under the hood, you can use any Docker Compose cli commands to interact with a running script, including manually restarting specific services with `docker-compose -f dev.docker-compose.yml restart <service name>`.

#### `test` script

Used to simplify running tests, without having to remember which unittest subcommands to use for test discovery.
Simply specify whether you want to run the unit or integration tests by passing the appropriate argument: `pj test unit` or `pj test integration`.

Aliases:

- `pj t [arguments...]` == `pj test [arguments...]`
- `pj test e2e` == `pj test integration`

#### `unit` command

Runs all tests discoverable as `test_*.py` in `./test/unit/`.

#### `integration` command

Runs all tests discoverable as `test_*.py` in `./test/integration/`.
Requires a running dev stack to run the tests against, as it works by consuming the service as an outside actor via AMQP.
The tests will error if the running dev stack's `db` service isn't using a schema to match the application.
Use `pj manage sync` to update the running `db` service's schema if needed.

#### `manage` script

`./scripts/manage` defers to `./manage.py` to expose two commands: `sync` & `pending`. These commands utilize [djrobstep/migra/](https://github.com/djrobstep/migra/) to handle database migrations.

##### `sync` command

This is the command you're likely to use the most during development.
It works by crawling `./src/models` for `sql` files, then reads the table definitions & other queries & compares them to the current schema definition of your running database in the development stack.
Finally, `sync` shows you a series of sql queries needed to synchronize your running dev database with the schema defined in your application's `./src/models/**/*.sql` files, & asks you if you want to run the queries & update your database.
If you want to, you can pass the `noprompt` argument (`pj manage sync noprompt`) to automatically apply the changes needed to synchronize your database to your application schema.

##### `pending` command

This command is used to define a migration for a production database.
It works by reading a schema dump defined at `./migrations/production.dump.sql`, then comparing that to your application schema defined across `./src/models/**/*.sql`, & finally saving the necessary queries required to update the production schema to match your application structure to `./migrations/pending.sql`.
You can then run the queries in `pending.sql` on you production database using `psql <database name> -U <user name> -h <production host> -f ./migrations/pending.sql`, assuming you have psql installed.

## Deployment

Deploy the service by building an image with `docker build -t <image name here> .`, then running that image in a production stack with either Docker Compose or Docker Swarm.
