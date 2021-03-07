"""
Test helper to handle publishing messages as Queue Producer to
a Queue for a Worker on an AMPQ broker.
"""

import gzip
import json
from typing import Any

import pika
from pika.adapters.blocking_connection import BlockingChannel

Connection = pika.BlockingConnection
Channel = BlockingChannel


# pylint: disable=too-few-public-methods
class Client:
    """Set up Queue Producer."""

    channel: Channel

    def __init__(
        self,
        channel: Channel
    ):
        self.channel = channel

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
