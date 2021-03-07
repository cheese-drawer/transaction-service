"""An example implementation of custom object Model."""

import json
from typing import Any, List, Dict

from psycopg2 import sql

from db_wrapper.model import ModelData, Model, Read, Create, Client


class ExampleItemData(ModelData):
    """An example Item."""

    # PENDS python 3.9 support in pylint,
    # ModelData inherits from TypedDict
    # pylint: disable=too-few-public-methods

    string: str
    integer: int
    json: Dict[str, Any]


class ExampleItemCreator(Create[ExampleItemData]):
    """Add custom json loading to Model.create."""

    # pylint: disable=too-few-public-methods

    async def one(self, item: ExampleItemData) -> ExampleItemData:
        """Override default Model.create.one method."""
        columns: List[sql.Identifier] = []
        values: List[sql.Literal] = []

        for column, value in item.items():
            if column == 'json':
                values.append(sql.Literal(json.dumps(value)))
            else:
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

        result: List[ExampleItemData] = \
            await self._client.execute_and_return(query)

        return result[0]


class ExampleItemReader(Read[ExampleItemData]):
    """Add custom method to Model.read."""

    async def all_by_string(self, string: str) -> List[ExampleItemData]:
        """Read all rows with matching `string` value."""
        query = sql.SQL(
            'SELECT * '
            'FROM {table} '
            'WHERE string = {string};'
        ).format(
            table=self._table,
            string=sql.Literal(string)
        )

        result: List[ExampleItemData] = await self \
            ._client.execute_and_return(query)

        return result


class ExampleItem(Model[ExampleItemData]):
    """Build an ExampleItem Model instance."""

    read: ExampleItemReader
    create: ExampleItemCreator

    def __init__(self, client: Client) -> None:
        super().__init__(client, 'example_item')
        self.read = ExampleItemReader(self.client, self.table)
        self.create = ExampleItemCreator(self.client, self.table)
