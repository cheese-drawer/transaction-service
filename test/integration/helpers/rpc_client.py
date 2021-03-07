"""Test helper to handle making RPC requests to an AMPQ broker."""

import gzip
import json
import uuid
import time
from typing import Any, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel

Connection = pika.BlockingConnection
Channel = BlockingChannel


class ResponseTimeout(Exception):
    pass


# pylint: disable=too-few-public-methods
class Client:
    """Set up RPC response consumer with handler & provide request caller."""

    channel: Channel
    connection: Connection
    correlation_id: str
    response: Any

    def __init__(
        self,
        connection: Connection,
        channel: Channel
    ):
        self.connection = connection
        self.channel = channel

        print('declaring response queue')

        result = self.channel.queue_declare(
            queue='', exclusive=True, auto_delete=True)
        self.callback_queue = result.method.queue

        print('listening on response queue')

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self._on_response,
            auto_ack=True)

    def _on_response(self, _: Any, __: Any, props: Any, body: bytes) -> None:
        if self.correlation_id == props.correlation_id:
            self.response = json.loads(gzip.decompress(body).decode('UTF8'))
            print(f'Response received {self.response}')

    # PENDS python 3.9 support in pylint
    # pylint: disable=unsubscriptable-object
    def call(
            self,
            target_queue: str,
            message: Optional[Any] = None,
            timeout: int = 5000) -> Any:
        """Send message as RPC Request to given queue & return Response."""
        self.response = None
        self.correlation_id = str(uuid.uuid4())
        message_props = pika.BasicProperties(
            reply_to=self.callback_queue,
            correlation_id=self.correlation_id)

        message_as_dict = {
            'data': message,
        }

        print(f'Sending message {message}')

        self.channel.basic_publish(
            exchange='',
            routing_key=target_queue,
            properties=message_props,
            body=gzip.compress(json.dumps(message_as_dict).encode('UTF8')))
        start_time = time.time()

        print('Message sent, waiting for response...')

        while self.response is None:
            if (start_time + timeout) < time.time():
                raise ResponseTimeout()

            self.connection.process_data_events(time_limit=timeout)

        # NOTE: mypy incorrectly thinks this statement is unreachable
        # what it doesn't know is that connection.process_data_events()
        # will call _on_response, setting self.response when a response
        # is received on the callback queue defined in __init__
        return self.response  # type: ignore
