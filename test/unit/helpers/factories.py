"""Factory methods for generating Test objects."""

from datetime import date
from uuid import uuid4

from src import models


class Location:

    @staticmethod
    def createOne() -> models.transaction.Location:
        return models.transaction.Location(
            address='123 Some Street',
            city='Some City',
            region='Some State',
            postal_code='Some Zip Code',
            country='Some Country',
            latitude=1,
            longitude=1,
            store_number=None,
        )


class TransactionData:

    @staticmethod
    def createOne() -> models.TransactionData:
        return models.TransactionData(
            _id=uuid4(),
            amount=1.00,
            pending=False,
            payee="A payee",
            date_authorized=date.today(),
            date=date.today(),
            spent_from_id=None,
            account_id=uuid4(),
            category=[],
            location=Location.createOne(),
            plaid_transaction_id="id_from_plaid"
        )
