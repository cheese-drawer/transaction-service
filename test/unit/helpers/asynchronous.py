"""Helpers for testing asynchronous code."""

import asyncio
from typing import Any, Awaitable, Callable
from unittest.mock import MagicMock


class AsyncMock(MagicMock):
    """Extend unittest.mock.MagicMock to allow mocking of async functions."""
    # pylint: disable=invalid-overridden-method
    # pylint: disable=useless-super-delegation

    async def __call__(self, *args, **kwargs):  # type: ignore
        return super().__call__(*args, **kwargs)


def async_test(
    test: Callable[[Any], Awaitable[None]]
) -> Callable[[Any], None]:
    """Decorate an async test method to run it in a one-off event loop."""
    def wrapped(instance: Any) -> None:
        asyncio.run(test(instance))

    return wrapped
