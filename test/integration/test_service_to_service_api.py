"""Tests for endpoints on the Request & Response API."""
# pylint: disable=missing-function-docstring

# from datetime import date
# import random
import unittest
from uuid import uuid1, UUID
import time
from typing import Any, Optional, List, Dict

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import register_adapter
from psycopg2.extras import Json, RealDictCursor  # type: ignore

# pylint thinks `test. ...` is a standard import for some reason
# pylint: disable=wrong-import-order
from test.integration.helpers.connection import connect, Connection, Channel
from test.integration.helpers.queue_client import Producer, Consumer
from test.integration.helpers.timeout import TimeLimitedTestCase

# tell psycopg2 to adapt all dictionaries to json instead of
# the default hstore
register_adapter(dict, Json)


connection: Connection
channel: Channel
producer: Producer

DSN = 'postgres://test:pass@localhost/dev'
TABLE_NAME = 'transaction'


def setUpModule() -> None:
    """Establish connection & create AMQP producer."""
    # pylint: disable=global-statement
    # pylint: disable=invalid-name
    global connection
    global channel
    global producer

    connection, channel = connect(
        host='localhost',
        port=8672,
        user='test',
        password='pass'
    )
    producer = Producer(channel)

    # clear database table
    _clear_table()


def tearDownModule() -> None:
    """Close connection."""
    # pylint: disable=global-statement
    # pylint: disable=invalid-name
    global connection
    connection.close()

    # clear database table
    _clear_table()


def _execute_query(query: sql.Composed) -> None:
    conn = psycopg2.connect(
        DSN,
        cursor_factory=RealDictCursor)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query)

    finally:
        conn.close()


def _execute_and_return(query: sql.Composed) -> Any:
    conn = psycopg2.connect(
        DSN,
        cursor_factory=RealDictCursor)

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query)
                result = cur.fetchall()

    finally:
        conn.close()

    return result


def _clear_table() -> None:
    _execute_query(
        sql.SQL('DELETE FROM {table}').format(
            table=sql.Identifier(TABLE_NAME)))


class Transaction:
    """Transaction Factory."""

    @staticmethod
    def create_with_id(tran_id: Optional[UUID] = None) -> Dict[str, Any]:
        return {
            'id': str(tran_id if not None else uuid1()),
            'amount': 1.0,
            'pending': False,
            'payee': 'a payee',
            'date_authorized': '2021-03-21',
            'date': '2021-03-21',
            'spent_from_id': None,
            'account_id': str(uuid1()),
            'category': ['Category'],
            'location': {},
            'plaid_transaction_id': 'a_plaid_id',
        }


class TestRouteTransactionNew(TimeLimitedTestCase):
    """Tests for API endpoint `queue-test`."""

    TEST_TIME_LIMIT = 120

    def tearDown(self) -> None:
        # clear all records from database table after every test
        _clear_table()

    def test_sending_transaction_adds_to_db(self) -> None:
        """Sending a transaction as json adds it to the database."""
        new_id = uuid1()
        message = {
            'transactions': [Transaction.create_with_id(new_id)],
        }
        producer.publish(
            'transaction.s2s.new',
            message)

        # because publish happens asynchronously, attempting to read the db
        # directly after publishing the new transaction data may occur before
        # the service has a chance to save the new record.
        time.sleep(0.1)

        query = sql.SQL(
            'SELECT * FROM {table}'
            'WHERE id = {id}'
        ).format(
            table=sql.Identifier(TABLE_NAME),
            id=sql.Literal(str(new_id)))

        db_result = _execute_and_return(query)

        with self.subTest():
            self.assertEqual(len(db_result), 1)
        with self.subTest():
            self.assertEqual(UUID(db_result[0]['id']), new_id)

    def test_can_add_many_transactions(self) -> None:
        """Sending many transactions adds all of them to the database."""
        num_records = 100
        tran_ids = [uuid1() for _ in range(0, num_records)]
        message = {
            'transactions': [
                Transaction.create_with_id(new_id) for new_id in tran_ids],
        }
        producer.publish(
            'transaction.s2s.new',
            message)

        # the length of time to wait must increase with the size of the
        # payload, as the worker needs extra time to transmit it (just barely)
        # and the database needs extra time to save the records (the bigger
        # problem)
        time.sleep(0.1)

        query = sql.SQL(
            'SELECT *'
            'FROM {table}'
        ).format(
            table=sql.Identifier(TABLE_NAME)
        )

        db_result = _execute_and_return(query)
        result_ids = [row['id'] for row in db_result]

        with self.subTest():
            self.assertEqual(len(db_result), num_records)
        with self.subTest():
            self.assertSetEqual(set(result_ids), {str(id) for id in tran_ids})

    def test_invalid_data_does_not_change_database(self) -> None:
        """Sending data unable to be validated as Transaction adds nothing."""
        message = {'transactions': [1, 2, 3]}
        producer.publish('transaction.s2s.new', message)
        query = sql.SQL(
            'SELECT *'
            'FROM {table}'
        ).format(
            table=sql.Identifier(TABLE_NAME)
        )

        db_result = _execute_and_return(query)

        self.assertEqual(len(db_result), 0)

    def test_invalid_data_logs_error(self) -> None:
        """Sending data unable to be validated as Transaction logs error."""
        # send a message that should result in an error for the service
        message = {'transactions': [1, 2, 3]}
        producer.publish('transaction.s2s.new', message)

        # check the logging queue for an error message
        log_queue = 'logger.error'
        logs: List[Any] = []
        last_message: Optional[Any] = None

        consumer = Consumer(channel)
        last_message = consumer.get(log_queue)

        while last_message is not None:
            logs.append(last_message)
            last_message = consumer.get(log_queue)

        print(logs)

        self.assertGreater(len(logs), 0)

    def test_skips_duplicate_ids(self) -> None:
        """Skips adding a transaction if it already exists in the database."""
        new_id = uuid1()
        tran1 = Transaction.create_with_id(new_id)
        tran1['payee'] = 'Original transaction'
        message1 = {'transactions': [tran1]}
        producer.publish('transaction.s2s.new', message1)
        # try adding another one with the same id
        tran2 = Transaction.create_with_id(new_id)
        tran2['payee'] = 'Duplicate transaction'
        message2 = {'transactions': [tran2]}
        producer.publish('transaction.s2s.new', message2)

        # because publish happens asynchronously, attempting to read the db
        # directly after publishing the new transaction data may occur before
        # the service has a chance to save the new record.
        time.sleep(0.1)

        query = sql.SQL(
            'SELECT * FROM {table}'
            'WHERE id = {id}'
        ).format(
            table=sql.Identifier(TABLE_NAME),
            id=sql.Literal(str(new_id)))

        db_result = _execute_and_return(query)

        with self.subTest():
            self.assertEqual(len(db_result), 1)
        with self.subTest():
            self.assertEqual(UUID(db_result[0]['id']), new_id)
        with self.subTest():
            self.assertEqual(db_result[0]['payee'], 'Original transaction')


if __name__ == '__main__':
    unittest.main()
