"""An example implementation of custom object Model."""

# import json
# from typing import Any, List, Dict
#
# from psycopg2 import sql
from datetime import date
from typing import Optional, List, TypedDict
from uuid import UUID

from db_wrapper.model import (
    ModelData,
    Model,
    # Read,
    # Create,
    # Client
)


class Location(TypedDict):
    """Geolocation data for a Transaction."""

    # PENDS python 3.9 support in pylint,
    # pylint: disable=too-few-public-methods

    address: Optional[str]
    city: Optional[str]
    region: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    store_number: Optional[str]


class TransactionData(ModelData):
    """An example Item."""

    # PENDS python 3.9 support in pylint,
    # ModelData inherits from TypedDict
    # pylint: disable=too-few-public-methods

    amount: float
    pending: bool
    payee: str
    # date charge was authorized
    # may not be the same as `TransactionData.date`
    date_authorized: date
    # date charge posted
    # (if still pending, date transaction occurred)
    date_posted: date
    spent_from_id: Optional[UUID]  # id of Budget Item
    account_id: UUID  # id of associated Bank Account
    category: List[str]  # Categories from Plaid? May change later...
    location: Location
    plaid_transaction_id: str  # id from Plaid


class Transaction(Model[TransactionData]):
    """Build an Transaction Model instance."""


# class TransactionCreator(Create[TransactionData]):
#     """Add custom json loading to Model.create."""
#
#     # pylint: disable=too-few-public-methods
#
#     async def one(self, item: TransactionData) -> TransactionData:
#         """Override default Model.create.one method."""
#         columns: List[sql.Identifier] = []
#         values: List[sql.Literal] = []
#
#         for column, value in item.items():
#             if column == 'json':
#                 values.append(sql.Literal(json.dumps(value)))
#             else:
#                 values.append(sql.Literal(value))
#
#             columns.append(sql.Identifier(column))
#
#         query = sql.SQL(
#             'INSERT INTO {table} ({columns}) '
#             'VALUES ({values}) '
#             'RETURNING *;'
#         ).format(
#             table=self._table,
#             columns=sql.SQL(',').join(columns),
#             values=sql.SQL(',').join(values),
#         )
#
#         result: List[TransactionData] = \
#             await self._client.execute_and_return(query)
#
#         return result[0]
#
#
# class TransactionReader(Read[TransactionData]):
#     """Add custom method to Model.read."""
#
#     async def all_by_string(self, string: str) -> List[TransactionData]:
#         """Read all rows with matching `string` value."""
#         query = sql.SQL(
#             'SELECT * '
#             'FROM {table} '
#             'WHERE string = {string};'
#         ).format(
#             table=self._table,
#             string=sql.Literal(string)
#         )
#
#         result: List[TransactionData] = await self \
#             ._client.execute_and_return(query)
#
#         return result
#
#
# class Transaction(Model[TransactionData]):
#     """Build an Transaction Model instance."""
#
#     read: TransactionReader
#     create: TransactionCreator
#
#     def __init__(self, client: Client) -> None:
#         super().__init__(client, 'example_item')
#         self.read = TransactionReader(self.client, self.table)
#         self.create = TransactionCreator(self.client, self.table)
