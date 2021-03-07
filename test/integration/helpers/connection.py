"""Test helper to establish connection & channel to & on AMQP broker."""

from time import sleep
from typing import Tuple, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel

Connection = pika.BlockingConnection
Channel = BlockingChannel
ConnectionParameters = pika.ConnectionParameters


def _try_connect(
    connection_params: ConnectionParameters,
    retries: int = 1
) -> Connection:
    host = connection_params.host
    port = connection_params.port

    # PENDS python 3.9 support in pylint
    # pylint: disable=unsubscriptable-object
    connection: Optional[Connection] = None

    print(f'Attempting to connect to broker at {host}:{port}...')

    while connection is None:
        try:
            connection = Connection(connection_params)
        except Exception as err:
            if retries > 12:
                raise Exception(
                    'Max number of connection attempts has been '
                    f'reached {retries}'
                ) from err

            print(
                f'Connection failed ({retries} time(s))'
                'retrying again in 5 seconds...')

            sleep(5)
            return _try_connect(connection_params, retries + 1)

    return connection


def connect(
    host: str,
    port: int,
    user: str,
    password: str,
) -> Tuple[Connection, Channel]:
    """Create a connection & channel a given broker."""
    credentials = pika.PlainCredentials(user, password)
    connection_parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials)

    connection = _try_connect(connection_parameters)

    return connection, connection.channel()
