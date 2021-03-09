"""Methods to help with testing database interactions."""

from typing import TypeVar, List
from psycopg2 import sql

from db_wrapper import Client, ConnectionParameters, ModelData
from .asynchronous import AsyncMock


def composed_to_string(seq: sql.Composed) -> str:
    """Test helper to convert a sql query to a string for comparison.

    Works for queries built with postgres.sql.Composable objects.
    From https://github.com/psycopg/psycopg2/issues/747#issuecomment-662857306
    """

    def compose_array(q: sql.Composed) -> List[str]:
        # print(f'composing {q}')
        strings: List[str] = []

        for p in q.seq:
            # print(f'working on adding {p}')
            # print(f'to {strings}')
            if isinstance(p, sql.Composed):
                strings = strings + compose_array(p)
            else:
                try:
                    strings.append(p.string)  # type: ignore
                except AttributeError:
                    strings.append(str(p.wrapped))  # type: ignore

        return strings

    return "".join(compose_array(seq))


def get_client() -> Client:
    """Create a client with placeholder connection data."""
    conn_params = ConnectionParameters('a', 'a', 'a', 'a')
    return Client(conn_params)


# Generic doesn't need a more descriptive name
# pylint: disable=invalid-name
T = TypeVar("T", bound=ModelData)


def mock_client(query_result: List[T]) -> Client:
    """
    Create a mocked client.

    Creates client with placeholder connection data using `get_client`,
    then mocks the `execute_and_return` method on it before returning it.
    Mocked method will return the value given as `query_result` argument.
    """
    client = get_client()

    # mock client's sql execution method
    client.execute_and_return = AsyncMock(  # type:ignore
        return_value=query_result)

    return client
