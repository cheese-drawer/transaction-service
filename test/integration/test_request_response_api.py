"""Tests for endpoints on the Request & Response API."""
# pylint: disable=missing-function-docstring

from datetime import date
import random
import unittest
from uuid import uuid1, UUID
from typing import List

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import register_adapter
from psycopg2.extras import Json

# pylint thinks `test. ...` is a standard import for some reason
# pylint: disable=wrong-import-order
from test.integration.helpers.connection import connect, Connection
from test.integration.helpers.rpc_client import Client
from test.integration.helpers.timeout import TimeLimitedTestCase

# tell psycopg2 to adapt all dictionaries to json instead of
# the default hstore
register_adapter(dict, Json)

connection: Connection
client: Client

TABLE_NAME = 'transaction'


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


def _rand_date() -> date:
    return date.fromordinal(
        date.today().toordinal() - random.randint(0, 100))


def _build_row(tran_id: UUID) -> sql.Composed:
    a_date = _rand_date()

    return sql.SQL(
        "({tran_id},'1.00',FALSE,'a payee',{date_authorized},{date},"
        "{acct_id},ARRAY [ 'Category' ], {location},'plaid_id')"
    ).format(
        tran_id=sql.Literal(str(tran_id)),
        date_authorized=sql.Literal(a_date),
        date=sql.Literal(a_date),
        acct_id=sql.Literal(str(uuid1())),
        location=sql.Literal({})
    )


def _populate(transaction_ids: List[UUID]) -> None:
    rows = sql.SQL(",").join([_build_row(tran_id)
                              for tran_id in transaction_ids])
    # inserts 1 row for each id into `transaction` table
    query = sql.SQL(
        "INSERT INTO {table} (id,amount,pending,payee,date_authorized,"
        "date,account_id,category,location,plaid_transaction_id) "
        "VALUES {rows};"
    ).format(
        table=sql.Identifier(TABLE_NAME),
        rows=rows,
    )
    conn = psycopg2.connect('postgres://test:pass@localhost/dev')

    # set db state to test against here
    try:
        with conn:
            with conn.cursor() as cur:
                # start by making sure it is empty
                cur.execute(f'DELETE FROM {TABLE_NAME}')
                # then insert test records
                cur.execute(query)

    finally:
        conn.close()


def _trim_msg_id(msg_id: str) -> str:
    """
    Trim string representation of UUID from response to hex only.

    Response has UUID as `UUID('bbcc5cc5-f893-411b-a5d8-aa765bfd0212')`
    when they're needed as `'bbcc5cc5-f893-411b-a5d8-aa765bfd0212'`
    for equality comparison.
    """

    print(f'msg_id: {msg_id}')
    split = msg_id.split("'")
    return split[1]


class TestRouteTransactionGet(TimeLimitedTestCase):
    """Tests for API endpoint `transaction.get`"""
    transaction_id: List[UUID]

    def setUp(self) -> None:
        super().setUp()

        self.transaction_ids = [uuid1() for _ in range(0, 100)]
        _populate(self.transaction_ids)

    def test_response_should_be_limited_to_50_records(self) -> None:
        data = client.call('transaction.get')['data']
        ids = [transaction['id']
               for transaction in data]

        with self.subTest():
            self.assertTrue(
                set(ids).issubset([str(i) for i in self.transaction_ids]))
        with self.subTest():
            self.assertEqual(len(data), 50)

    def test_response_can_be_given_new_limit(self) -> None:
        data = client.call('transaction.get', {'count': 10})['data']

        with self.subTest():
            self.assertEqual(len(data), 10)

    def test_limit_cant_be_greater_than_50(self) -> None:
        response = client.call('transaction.get', {'count': 51})

        with self.subTest():
            self.assertFalse(response['success'])
        with self.subTest():
            self.assertIn(
                'can not be greater than 50',
                response['error']['message'])

    def test_response_can_be_paginated_with_limit_and_offset(self) -> None:
        first_ten = client.call('transaction.get', {'count': 10})['data']
        next_ten = client.call(
            'transaction.get', {
                'count': 10, 'offset': 10})['data']
        print(f'next_ten: {next_ten}')
        next_ten_ids = [tran['id'] for tran in next_ten]

        for tran in first_ten:
            with self.subTest():
                self.assertNotIn(tran['id'], next_ten_ids)
        with self.subTest():
            self.assertGreaterEqual(first_ten[-1]['date'], next_ten[0]['date'])

    def test_the_results_are_sorted_in_reverse_chronological_order(
        self
    ) -> None:
        data = client.call('transaction.get')['data']

        previous: date
        current: date

        for index, transaction in enumerate(data):
            current = date.fromisoformat(transaction['date'])

            if index != 0:
                # print(f'{index})')
                # print(
                #     f'previous ({previous}) >= current ({current}): '
                #     f'{previous >= current}')
                # print(
                #     f'previous {type(previous)}, current {type(current)}')

                with self.subTest():
                    self.assertGreaterEqual(previous, current)

            previous = current

    def test_a_single_transaction_can_be_retrieved_by_its_id(self) -> None:
        tran_id = str(self.transaction_ids[0])
        data = client.call(
            'transaction.get',
            {'id': tran_id}
        )['data']

        with self.subTest():
            self.assertEqual(len(data), 1)
        with self.subTest():
            self.assertEqual(
                tran_id,
                data[0]['id'])

    def test_count_and_offset_are_ignored_when_retrieving_one_by_id(
        self
    ) -> None:
        tran_id = str(self.transaction_ids[0])
        data = client.call(
            'transaction.get',
            {'id': tran_id,
             'count': 10,
             'offset': 10}
        )['data']

        with self.subTest():
            self.assertEqual(len(data), 1)
        with self.subTest():
            self.assertEqual(
                tran_id,
                data[0]['id'])

    def test_an_error_is_returned_when_no_matching_id_is_found(self) -> None:
        tran_id = str(uuid1())
        response = client.call(
            'transaction.get',
            {'id': tran_id}
        )

        with self.subTest():
            self.assertFalse(response['success'])


class TestRouteTransactionUpdate(TimeLimitedTestCase):
    """Tests for API endpoint `transaction.update`"""
    transaction_id: List[UUID]

    def setUp(self) -> None:
        super().setUp()

        self.transaction_ids = [uuid1() for _ in range(0, 2)]
        _populate(self.transaction_ids)

    def test_updates_one_or_more_given_fields_on_transaction_with_given_id(
        self
    ) -> None:
        tran_id = str(self.transaction_ids[0])
        new_spent_from_id = uuid1()
        data = client.call(
            'transaction.update',
            {'transaction_id': tran_id,
             'changes': {
                 'spent_from_id': str(new_spent_from_id)
             }}
        )['data']

        self.assertEqual(
            data[0]['spent_from_id'],
            str(new_spent_from_id))

    def test_changes_passed_to_update_persist_in_database(self) -> None:
        tran_id = str(self.transaction_ids[0])
        new_spent_from_id = uuid1()
        client.call(
            'transaction.update',
            {'transaction_id': tran_id,
             'changes': {
                 'spent_from_id': str(new_spent_from_id)
             }}
        )

        from_db = client.call(
            'transaction.get',
            {'id': tran_id}
        )['data']

        self.assertEqual(
            from_db[0]['spent_from_id'],
            str(new_spent_from_id))


if __name__ == '__main__':
    unittest.main()
