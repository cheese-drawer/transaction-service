"""An example implementation of custom object Model."""

import datetime
import json
from typing import (
    Any,
    Union,
    Optional,
    List,
    Dict,
)
from uuid import UUID

# pydantic is a C module & pylint can't parse it without loading
# it into the Python interpreter using --extension-pkg-whitelist
# or just ignore it anyways since MyPy's able to parse it instead
# and validates that BaseModel exists
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from psycopg2 import sql

from db_wrapper.model import (
    Client,
    ModelData,
    Model,
    Create,
    Read,
)


class Location(BaseModel):
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


class TransactionCreator(Create[TransactionData]):
    """Add custom location parsing to Transaction.create."""

    # pylint: disable=too-few-public-methods

    @staticmethod
    def _build_row(item: TransactionData) -> sql.Composed:
        values: List[Union[sql.Literal, sql.Composed]] = []

        for column, value in item.dict().items():
            if column == 'location':
                values.append(sql.Literal(json.dumps(value)))
            else:
                values.append(sql.Literal(value))

        values_composed = sql.SQL(',').join(values)

        return sql.SQL('({row})').format(row=values_composed)

    async def one(self, item: TransactionData) -> TransactionData:
        """Override default Model.create.one method."""
        columns: List[sql.Identifier] = []
        row = self._build_row(item)

        for column in item.dict().keys():
            columns.append(sql.Identifier(column))

        query = sql.SQL(
            'INSERT INTO {table} ({columns}) '
            'VALUES {row} '
            'RETURNING *;'
        ).format(
            table=self._table,
            columns=sql.SQL(',').join(columns),
            row=row,
        )

        result: List[TransactionData] = \
            await self._client.execute_and_return(query)

        return result[0]

    async def many(
        self,
        records: List[TransactionData]
    ) -> List[TransactionData]:
        """Insert many Transactions into the table simultaneously."""
        columns: List[sql.Identifier] = []
        rows = [self._build_row(record) for record in records]

        for column in records[0].dict().keys():
            columns.append(sql.Identifier(column))

        query = sql.SQL(
            'INSERT INTO {table} ({columns}) '
            'VALUES {row} '
            'RETURNING *;'
        ).format(
            table=self._table,
            columns=sql.SQL(',').join(columns),
            row=sql.SQL(',').join(rows),
        )

        result: List[TransactionData] = \
            await self._client.execute_and_return(query)

        return result


class TransactionReader(Read[TransactionData]):
    """Add custom method to Model.read."""

    async def many(
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

        results: List[Dict[str, Any]] = \
            await self._client.execute_and_return(query)

        return [TransactionData(**result) for result in results]


class Transaction(Model[TransactionData]):
    """Build an Transaction Model instance."""

    read: TransactionReader
    create: TransactionCreator

    def __init__(self, client: Client) -> None:
        super().__init__(client, 'transaction')
        self.read = TransactionReader(self.client, self.table)
        self.create = TransactionCreator(self.client, self.table)
