"""Encapsulates logic used to actually run the application.

Provided as an abstraction to avoid errors in configuration
while defining application logic in main.py.
"""

import asyncio
from logging import getLogger
import signal
from typing import Any, Protocol, Awaitable, Callable, List


LOGGER = getLogger(__name__)


class Connectable(Protocol):
    """Protocol specifying that object has connection methods.

    Requires that an object have the following methods & signatures:

        async connect() -> None
        async disconnect() -> None
    """

    def connect(self) -> Awaitable[None]:
        """Connect to the defined i/o service then return this instance."""
        ...

    def disconnect(self) -> Awaitable[None]:
        """Connect to the defined i/o service then return this instance."""
        ...


class Runnable(Protocol):
    """Protocol specifying that a 'runnable' object.

    Requires object to have a `run` method that returns an async function
    that resolves to none when called.
    """

    # PENDS python 3.9 support in pylint
    # pylint: disable=too-few-public-methods

    def run(self) -> Awaitable[Callable[[], Awaitable[None]]]:
        """Run the object implementing a Runnable protocol."""
        ...


class Runner:
    """Simple helper to handle graceful exits."""

    exiting: bool
    databases: List[Connectable]
    workers: List[Runnable]
    stoppers: List[Callable[[], Awaitable[None]]]

    def __init__(self) -> None:
        signal.signal(signal.SIGINT, self._quit)
        signal.signal(signal.SIGTERM, self._quit)

        self.exiting = False
        self.databases = []
        self.workers = []
        self.stoppers = []

    async def _connect_databases(self) -> Any:
        return await asyncio.gather(
            *[database.connect() for database in self.databases])

    async def _disconnect_databases(self) -> Any:
        return await asyncio.gather(
            *[database.disconnect() for database in self.databases])

    async def _run_workers(self) -> Any:
        """Gather registered workers & await them to execute in event loop."""
        return await asyncio.gather(*[worker.run() for worker in self.workers])

    async def _stop_workers(self) -> Any:
        """Collect worker stop methods & await them."""
        return await asyncio.gather(*[stop() for stop in self.stoppers])

    @staticmethod
    def _quit(signum: int, _: Any) -> None:
        """Exit the process by raising an Exception."""
        LOGGER.info(f'Exit signal received: {signum}')
        raise SystemExit(0)

    def register_database(self, database: Connectable) -> None:
        """Add database to list to be connected to when application is run."""
        self.databases.append(database)

    def register_worker(self, worker: Runnable) -> None:
        """Add worker to list to be run when application is run.

        Executes worker in asyncio event loop. Allows multiple workers
        by taking all workers registered via this method, then using
        asyncio.gather to execute all in parallel.
        """
        self.workers.append(worker)

    def run(self) -> None:
        """Run all registered workers in asyncio loop.

        Gracefully exit using SIGINT or SIGTERM.
        """
        # setup an event loop w/ asyncio
        loop = asyncio.get_event_loop()
        # tell it to establish database connection
        loop.run_until_complete(self._connect_databases())
        # tell it to start the workers & assign the result to variable
        # to be used later to stop the workers
        self.stoppers = loop.run_until_complete(self._run_workers())

        try:
            loop.run_forever()
        except SystemExit:
            # but setup graceful exit when error is raised in self._quit
            LOGGER.info('SystemExit caught, stopping workers...')
        finally:
            # by allowing worker to stop completely before killing process
            loop.run_until_complete(self._stop_workers())
            # and by allowing database connection to close
            loop.run_until_complete(self._disconnect_databases())

        loop.close()
