"""Tests for endpoints on the Request & Response API."""
# pylint: disable=missing-function-docstring

import unittest
from unittest import TestCase
from uuid import uuid4
from typing import Any, List, Dict

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import register_adapter
from psycopg2.extras import Json

from helpers.connection import connect, Connection
from helpers.rpc_client import Client


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
    client = Client(connection, channel)


def tearDownModule() -> None:
    """Close connection."""
    # pylint: disable=global-statement
    # pylint: disable=invalid-name
    global connection
    connection.close()


class TestRouteTest(TestCase):
    """Tests for API endpoint `test`."""

    def test_response_should_be_successful(self) -> None:
        successful = client.call('test', 'message')['success']

        self.assertTrue(successful)

    def test_response_appends_that_took_forever_to_message(
        self
    ) -> None:
        print('running test_response_appends_that_took_forever_to_message')
        data = client.call('test', 'message')['data']

        self.assertEqual(data, 'message that took forever')


class TestRouteWillError(TestCase):
    """Tests for API endpoint `will-error`."""
    response: Dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.response = client.call('will-error', '')

    def test_response_should_not_be_successful(self) -> None:
        successful = self.response['success']

        self.assertFalse(successful)

    def test_response_should_include_error_information(self) -> None:
        self.assertIn('error', self.response)

    def test_error_data_includes_message(self) -> None:
        message = client.call('will-error', 'message')['error']['message']

        for phrase in ['Just an exception', 'message']:
            # Using `self.subTest` as context allows for more elegance when
            # making multiple assertions in the same test. Instead of stopping
            # test execution if an assertion fails, it records the failure &
            # continues to make the remaining assertions.
            with self.subTest():
                self.assertIn(phrase, message)

    def test_error_data_includes_error_type(self) -> None:
        errtype = self.response['error']['type']

        self.assertEqual(errtype, 'Exception')


class TestRouteDictionary(TestCase):
    """Tests for API endpoint `dictionary`"""

    def test_response_should_include_original_dicts_attributes(
        self
    ) -> None:
        message = {
            'dictionary': 'foo'
        }
        response = client.call('dictionary', message)

        self.assertIn('dictionary', response['data'])

    def test_response_should_include_new_bar_attribute_with_value_baz(
        self
    ) -> None:
        message = {
            'dictionary': 'foo'
        }
        response = client.call('dictionary', message)

        self.assertEqual('baz', response['data']['bar'])


class TestRouteDb(TestCase):
    """Tests for API endpoint `db`"""

    def test_response_should_be_list_of_table_names(self) -> None:
        response = client.call('db')

        with self.subTest():
            self.assertIn('simple', response['data'])
        with self.subTest():
            self.assertIn('example_item', response['data'])

    def test_response_unaltered_by_message_content(self) -> None:
        response = client.call('db', 'this is ignored')

        with self.subTest():
            self.assertIn('simple', response['data'])
        with self.subTest():
            self.assertIn('example_item', response['data'])


class TestRouteExampleItems(TestCase):
    """Tests for API endpoint `db`"""
    example_items: List[Any]

    def setUp(self) -> None:
        self.example_items: List[Any] = [{
            '_id': uuid4(),
            'string': 'match me',
            'integer': 1,
            'json': {},
        }, {
            '_id': uuid4(),
            'string': 'match me',
            'integer': 1,
            'json': {},
        }, {
            '_id': uuid4(),
            'string': "don't match me",
            'integer': 1,
            'json': {},
        }]

        def example_item_query(item: Any) -> psycopg2.sql.Composed:
            base = sql.SQL(
                'INSERT INTO example_item (_id, string, integer, json) '
                'VALUES ({_id}, {string}, {integer}, {json});')
            query = base.format(
                _id=sql.Literal(str(item['_id'])),
                string=sql.Literal(item['string']),
                integer=sql.Literal(item['integer']),
                json=sql.Literal(item['json']))

            return query

        # tell psycopg2 to adapt all dictionaries to json instead of
        # the default hstore
        register_adapter(dict, Json)

        conn = psycopg2.connect('postgres://test:pass@localhost/dev')

        # set db State to test against here
        try:
            with conn:
                with conn.cursor() as cur:
                    # start by making sure it is empty
                    cur.execute('DELETE FROM example_item')
                    # cur.execute('DELETE * FROM simple')
                    # then insert test records
                    for item in self.example_items:
                        cur.execute(example_item_query(item))

        finally:
            conn.close()

    def test_response_should_be_include_all_records_with_matching_string_value(
        self
    ) -> None:
        def trim_msg_id(msg_id: str) -> str:
            """
            Trim string representation of UUID from response to hex only.

            Response has UUID as `UUID('bbcc5cc5-f893-411b-a5d8-aa765bfd0212')`
            when they're needed as `'bbcc5cc5-f893-411b-a5d8-aa765bfd0212'`
            for equality comparison.
            """

            split = msg_id.split("'")
            return split[1]

        def id_to_str(item: Any) -> str:
            return str(item['_id'])

        response = client.call('example-items', 'match me')
        ids = [trim_msg_id(item['_id']) for item in response['data']]

        with self.subTest():
            self.assertIn(id_to_str(self.example_items[0]), ids)
        with self.subTest():
            self.assertIn(id_to_str(self.example_items[1]), ids)
        with self.subTest():
            self.assertNotIn(id_to_str(self.example_items[2]), ids)

    def test_response_should_be_empty_if_no_matching_records_are_found(
        self
    ) -> None:
        response = client.call('example-items', 'match nothing')

        self.assertEqual(len(response['data']), 0)

    def test_response_should_be_error_if_no_query_string_is_given(
        self
    ) -> None:
        response = client.call('example-items')

        self.assertFalse(response['success'])


if __name__ == '__main__':
    unittest.main()
