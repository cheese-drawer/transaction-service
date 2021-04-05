"""
Test helper to handle publishing messages as Queue Producer to
a Queue for a Worker on an AMPQ broker.
"""

import gzip
import json
from typing import Any, Callable, Dict
import signal

import pika
from pika.adapters.blocking_connection import BlockingChannel

Connection = pika.BlockingConnection
Channel = BlockingChannel


class QueueBase:
    """Set up Queue Producer or Consumer."""

    # pylint: disable=too-few-public-methods

    channel: Channel

    def __init__(
        self,
        channel: Channel
    ):
        self.channel = channel


class Producer(QueueBase):
    """Set up Queue Producer."""

    # pylint: disable=too-few-public-methods

    def publish(
        self,
        target_queue: str,
        message: Any,
    ) -> None:
        """Send message as Queue Producer for Worker to consume."""
        message_as_dict = {
            'data': message,
        }

        self.channel.basic_publish(
            exchange='',
            routing_key=target_queue,
            body=gzip.compress(json.dumps(message_as_dict).encode('UTF8')),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )


Handler = Callable[[Dict[str, Any]], None]


class Consumer(QueueBase):
    """Set up Queue Consumer."""

    # pylint: disable=too-few-public-methods

    def get(
        self,
        target_queue: str,
    ) -> Any:
        """Get, decompress, decode, & de-serialize single message, if exist."""
        self.channel.queue_declare(queue=target_queue, durable=True)
        method, _, body = self.channel.basic_get(queue=target_queue)

        if method is not None:
            message = json.loads(
                gzip.decompress(body).decode('UTF8'))  # type: ignore
            self.channel.basic_ack(
                delivery_tag=method.delivery_tag)  # type: ignore

            return message

        return None
