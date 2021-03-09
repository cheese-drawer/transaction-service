"""Tests for models.transaction.

These tests are limited by mocking of Client's ability to query Postgres. This
means that actual SQL queries aren't being tested, just the processing of any
results received & the act of building a SQL query (without executing it).
"""
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods

import unittest
from unittest import TestCase
import json
from typing import cast

from helpers import factories
from helpers.asynchronous import async_test, AsyncMock
from helpers.database import mock_client, composed_to_string

from src.models.transaction import Transaction


class TestCreateOne(TestCase):
    """Testing Transaction model's create.one method."""

    @async_test
    async def test_it_correctly_builds_query_with_given_data(self) -> None:
        transaction = factories.TransactionData.createOne(
        )  # pylint: disable=unsubscriptable-object
        client = mock_client([transaction])
        model = Transaction(client)

        # PENDS python 3.9 support in pylint

        await model.create.one(transaction)

        query_composed = cast(
            AsyncMock, client.execute_and_return).call_args[0][0]
        query = composed_to_string(query_composed)

        expected_columns = '_id' \
            ',amount' \
            ',pending' \
            ',payee' \
            ',date_authorized' \
            ',date' \
            ',spent_from_id' \
            ',account_id' \
            ',category' \
            ',location' \
            ',plaid_transaction_id'
        expected_values = f"{transaction['_id']}," \
            f"{transaction['amount']}," \
            f"{transaction['pending']}," \
            f"{transaction['payee']}," \
            f"{transaction['date_authorized']}," \
            f"{transaction['date']}," \
            f"{transaction['spent_from_id']}," \
            f"{transaction['account_id']}," \
            f"{transaction['category']}," \
            f"{json.dumps(transaction['location'])}," \
            f"{transaction['plaid_transaction_id']}"

        self.assertEqual(
            query,
            f'INSERT INTO transaction ({expected_columns}) '
            f"VALUES ({expected_values}) "
            'RETURNING *;')


class TestReadAll(TestCase):
    """Testing Transaction.read.all method."""

    @async_test
    async def test_it_correctly_builds_query(self) -> None:
        transaction = factories.TransactionData.createOne(
        )  # pylint: disable=unsubscriptable-object
        client = mock_client([transaction])
        model = Transaction(client)

        await model.read.all()

        query_composed = cast(
            AsyncMock, client.execute_and_return).call_args[0][0]
        query = composed_to_string(query_composed)

        self.assertEqual(
            query, 'SELECT * FROM transaction ORDER BY date DESC;')


if __name__ == '__main__':
    unittest.main()
