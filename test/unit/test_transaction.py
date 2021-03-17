"""Tests for src/lib.py"""
# pylint: disable=missing-function-docstring

import unittest
from unittest import TestCase
from uuid import uuid4, UUID

from test.unit.helpers import factories

from src.transaction import Transaction


class TestUpdateSpentFrom(TestCase):
    """Tests for Transaction.update_spend_from"""

    original_transaction: Transaction
    updated_transaction: Transaction
    new_spent_from_id: UUID

    @classmethod
    def setUpClass(cls) -> None:
        cls.original_transaction = Transaction(
            factories.TransactionData.createOne())
        cls.new_spent_from_id = uuid4()

        cls.updated_transaction = cls.original_transaction.update_spent_from(
            cls.new_spent_from_id)

    def test_returns_a_new_transaction_with_updated_spent_from_field(
        self
    ) -> None:
        self.assertEqual(
            self.new_spent_from_id,
            self.updated_transaction.spent_from_id)

    def test_without_changing_the_previous_transaction_instance(self) -> None:
        self.assertNotEqual(
            self.original_transaction.spent_from_id,
            self.updated_transaction.spent_from_id)


if __name__ == '__main__':
    unittest.main()
