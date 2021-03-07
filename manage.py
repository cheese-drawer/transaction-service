"""Script for managing database migrations.

Exposes two methods:
    sync        diff app to live db & apply changes, use for dev primarily
    pending     diff schema dump & save to file, used for prod primarily
"""

from contextlib import contextmanager
import io
import os
import random
import string
import sys
import time
from typing import Any, Optional, Generator, List, Tuple

from migra import Migration  # type: ignore
from psycopg2 import connect, OperationalError  # type: ignore
from psycopg2 import sql
from psycopg2.sql import Composed
from sqlbag import (  # type: ignore
    S,
    load_sql_from_folder,
    load_sql_from_file)

# DB_USER = os.getenv('DB_USER', 'postgres')
# DB_PASS = os.getenv('DB_PASS', 'postgres')
# DB_HOST = os.getenv('DB_HOST', 'localhost')
# DB_NAME = os.getenv('DB_NAME', 'postgres')
DB_USER = os.getenv('DB_USER', 'test')
DB_PASS = os.getenv('DB_PASS', 'pass')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'dev')

DB_URL = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}'


def _try_connect(dsn: str, retries: int = 1) -> Any:
    # PENDS python 3.9 support in pylint
    # pylint: disable=unsubscriptable-object
    connection: Optional[Any] = None

    print(f'Attempting to connect to database at {dsn}')

    while connection is None:
        try:
            connection = connect(dsn)
        except OperationalError as err:
            print(type(err))
            if retries > 12:
                raise ConnectionError(
                    'Max number of connection attempts has been reached (12)'
                ) from err

            print(
                f'Connection failed ({retries} time(s))'
                'retrying again in 5 seconds...')

            time.sleep(5)
            return _try_connect(dsn, retries + 1)

    return connection


def _resilient_connect(dsn: str) -> Any:
    """Handle connecting to db, attempt to reconnect on failure."""
    return _try_connect(dsn)


def _prompt(question: str) -> bool:
    """Prompt user with simple yes/no question & return True if answer is y."""
    print(f'{question} ', end='')
    return input().strip().lower() == 'y'


def _temp_name() -> str:
    """
    Generate a temporary name.

    Prefixes a string of 10 random characters with 'temp_db' & returns it.
    """
    random_letters = [random.choice(string.ascii_lowercase) for _ in range(10)]
    rnd = "".join(random_letters)
    tempname = 'temp_db' + rnd

    return tempname


def _create_db(cursor: Any, name: str) -> None:
    """Create a database with a given name."""
    query = sql.SQL('create database {name};').format(
        name=sql.Identifier(name))

    cursor.execute(query)


def _kill_query(dbname: str) -> Composed:
    """Build & return SQL query that kills connections to a given database."""
    query = """
    SELECT
        pg_terminate_backend(pg_stat_activity.pid)
    FROM
        pg_stat_activity
    WHERE
        pg_stat_activity.datname = {dbname}
        AND pid <> pg_backend_pid();
    """

    return sql.SQL(query).format(dbname=sql.Literal(dbname))


def _drop_db(cursor: Any, name: str) -> None:
    """Drop a database with a given name."""
    revoke: Composed = sql.SQL(
        'REVOKE CONNECT ON DATABASE {name} FROM PUBLIC;'
    ).format(
        name=sql.Identifier(name))

    kill_other_connections: Composed = _kill_query(name)

    drop: Composed = sql.SQL('DROP DATABASE {name};').format(
        name=sql.Identifier(name))

    cursor.execute(revoke)
    cursor.execute(kill_other_connections)
    cursor.execute(drop)


def _load_pre_migration(dsn: str) -> None:
    """
    Load schema for production server.

    Uses sql schema file saved at migrations/production.dump.sql
    """
    connection = _resilient_connect(dsn)
    connection.set_session(autocommit=True)

    with connection.cursor() as cursor:
        cursor.execute(open('migrations/production.dump.sql', 'r').read())

    connection.close()


def _load_from_app(session: S) -> None:
    """
    Load schema from application source.

    Uses all .sql files stored at ./src/models/**
    """
    load_sql_from_folder(session, 'src/models')


@contextmanager
def _get_schema_diff(
    from_db_url: str,
    target_db_url: str
) -> Generator[Tuple[str, Migration], Any, Any]:
    """Get schema diff between two databases using djrobstep/migra."""
    with S(from_db_url) as from_schema_session, \
            S(target_db_url) as target_schema_session:
        migration = Migration(
            from_schema_session,
            target_schema_session)
        migration.set_safety(False)
        migration.add_all_changes()

        yield migration.sql, migration


@contextmanager
def _temp_db(host: str, user: str, password: str) -> Generator[str, Any, Any]:
    """Create, yield, & remove a temporary database as context."""
    connection = _resilient_connect(
        f'postgres://{user}:{password}@{host}/{DB_NAME}')
    connection.set_session(autocommit=True)
    name = _temp_name()

    with connection.cursor() as cursor:
        _create_db(cursor, name)
        yield f'postgres://{user}:{password}@{host}/{name}'
        _drop_db(cursor, name)

    connection.close()


def sync(args: List[str]) -> None:
    """
    Compare live database to application schema & apply changes to database.

    Uses running database specified for application via
    `DB_[USER|PASS|HOST|NAME]` environment variables & compares to application
    schema defined at `./src/models/**/*.sql`.
    """
    # define if prompts are needed or not
    no_prompt = False

    if 'noprompt' in args:
        no_prompt = True

    # create temp database for app schema
    with _temp_db(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS
    ) as temp_db_url:
        print(f'db url: {DB_URL}')
        print(f'temp url: {temp_db_url}')

        # create sessions for current db state & target schema
        with S(DB_URL) as from_schema_session, \
                S(temp_db_url) as target_schema_session:
            # load target schema to temp db
            _load_from_app(target_schema_session)

            # diff target db & current db
            migration = Migration(
                from_schema_session,
                target_schema_session)
            migration.set_safety(False)
            migration.add_all_changes()

            # handle changes
            if migration.statements:
                print('\nTHE FOLLOWING CHANGES ARE PENDING:', end='\n\n')
                print(migration.sql)

                if no_prompt:
                    print('Applying...')
                    migration.apply()
                    print('Changes applied.')
                else:
                    if _prompt('Apply these changes?'):
                        print('Applying...')
                        migration.apply()
                        print('Changes applied.')
                    else:
                        print('Not applying.')

            else:
                print('Already synced.')


def pending(_: List[str]) -> None:
    """
    Compare a production schema to application schema & save difference.

    Uses production schema stored at `./migrations/production.dump.sql` &
    application schema defined at `./src/models/**/*.sql`, then saves
    difference at `./migrations/pending.sql`.
    """
    # create temporary databases for prod & target schemas
    with _temp_db(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS
    ) as prod_schema_db_url, _temp_db(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS
    ) as target_db_url:
        print(f'prod temp url: {prod_schema_db_url}')
        print(f'target temp url: {target_db_url}')

        # create sessions for both databases
        with S(prod_schema_db_url) as from_schema_session, \
                S(target_db_url) as target_schema_session:
            # load both schemas into their databases
            _load_pre_migration(prod_schema_db_url)
            _load_from_app(target_schema_session)

            # get a diff
            migration = Migration(
                from_schema_session,
                target_schema_session)
            migration.set_safety(False)
            migration.add_all_changes()

            if migration.statements:
                print('\nTHE FOLLOWING CHANGES ARE PENDING:', end='\n\n')
                print(migration.sql)
            else:
                print('No changes needed, setting pending.sql to empty.')

            # write pending changes to file
            with io.open('migrations/pending.sql', 'w') as file:
                file.write(migration.sql)

            print('Changes written to ./migrations/pending.sql.')


if __name__ == '__main__':
    tasks = {
        'sync': sync,
        'pending': pending,
    }

    print(f'task: { sys.argv[1] }')

    try:
        ARGS: List[str] = []

        try:
            ARGS = sys.argv[2:]
        except IndexError:
            ARGS = []

        tasks[sys.argv[1]](ARGS)
    except KeyError:
        print('No such task')
    except IndexError:
        print('No task given')
