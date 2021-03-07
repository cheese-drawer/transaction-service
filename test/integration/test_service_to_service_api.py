"""Tests for endpoints on the Request & Response API."""
# pylint: disable=missing-function-docstring

import unittest
from unittest import TestCase

from helpers.connection import connect, Connection
from helpers.queue_client import Client


connection: Connection
client: Client


def setUpModule() -> None:
    """Establish connection & create AMQP client."""
    # pylint: disable=global-statement
    # pylint: disable=invalid-name
    global connection
    global client

    connection, channel = connect(
        host='localhost',
        port=8672,
        user='test',
        password='pass'
    )
    client = Client(channel)


def tearDownModule() -> None:
    """Close connection."""
    # pylint: disable=global-statement
    # pylint: disable=invalid-name
    global connection
    connection.close()


class TestRouteQueueTest(TestCase):
    """Tests for API endpoint `queue-test`."""

    def test_nothing_is_returned(self) -> None:
        """
        Nothing is returned.

        This example is a pretty useless test, instead it should probably
        eventually be paired with a Request via the R&R API to check if the
        side effects from pushing a message on the StS API had the desired
        side effect on the service.

        Such a test would do something like the following:

        1st: Setup initial state
        2nd: Push message via StS API
        3rd: Make R&R again, assert Response changed as expected
        """
        result = client.publish('queue-test', {'a': 1})  # type: ignore

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
