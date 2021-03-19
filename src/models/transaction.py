"""An example implementation of custom object Model."""

import datetime
from typing import Union, Optional, List, TypedDict
from uuid import UUID

from psycopg2 import sql
from psycopg2.extensions import register_adapter
from psycopg2.extras import Json

from db_wrapper.model import (
    ModelData,
    Model,
    Read,
    Create,
    Client
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
    date_authorized: datetime.date
    # date charge posted
    # (if still pending, date transaction occurred)
    date: datetime.date
    spent_from_id: Optional[UUID]  # id of Budget Item
    account_id: UUID  # id of associated Bank Account
    category: List[str]  # Categories from Plaid? May change later...
    location: Location
    plaid_transaction_id: str  # id from Plaid


# tell psycopg2 to adapt all dictionaries to json instead of
# the default hstore
register_adapter(dict, Json)


class TransactionCreator(Create[TransactionData]):
    """Add custom location parsing to Transaction.create."""

    # pylint: disable=too-few-public-methods

    async def one(self, item: TransactionData) -> TransactionData:
        """Override default Model.create.one method."""
        columns: List[sql.Identifier] = []
        values: List[Union[sql.Literal, sql.Composed]] = []

        for column, value in item.items():
            # if column == 'location':
            #     values.append(sql.Literal(json.dumps(value)))
            # else:
            #     values.append(sql.Literal(value))
            values.append(sql.Literal(value))

            columns.append(sql.Identifier(column))

        query = sql.SQL(
            'INSERT INTO {table} ({columns}) '
            'VALUES ({values}) '
            'RETURNING *;'
        ).format(
            table=self._table,
            columns=sql.SQL(',').join(columns),
            values=sql.SQL(',').join(values),
        )

        result: List[TransactionData] = \
            await self._client.execute_and_return(query)

        return result[0]


class TransactionReader(Read[TransactionData]):
    """Add custom method to Model.read."""

    async def all(
        self,
        count: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[TransactionData]:
        """Get all Transactions from the Database."""
        if count is None:
            count = 50
        if count > 50:
            raise ValueError('Parameter `count` can not be greater than 50.')
        if offset is None:
            offset = 0

        query = sql.SQL(
            'SELECT * '
            'FROM {table} '
            'ORDER BY date DESC '
            'LIMIT {count} OFFSET {offset};'
        ).format(
            table=self._table,
            count=sql.Literal(count),
            offset=sql.Literal(offset))

        result: List[TransactionData] = \
            await self._client.execute_and_return(query)

        return result


class Transaction(Model[TransactionData]):
    """Build an Transaction Model instance."""

    read: TransactionReader
    create: TransactionCreator

    def __init__(self, client: Client) -> None:
        super().__init__(client, 'transaction')
        self.read = TransactionReader(self.client, self.table)
        self.create = TransactionCreator(self.client, self.table)
