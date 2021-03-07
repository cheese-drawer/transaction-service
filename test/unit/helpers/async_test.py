"""Helpers for testing asynchronous code."""

import asyncio
from typing import Any, Awaitable, Callable


def async_test(
    test: Callable[[Any], Awaitable[None]]
) -> Callable[[Any], None]:
    """Decorate an async test method to run it in a one-off event loop."""
    def wrapped(instance: Any) -> None:
        asyncio.run(test(instance))

    return wrapped
