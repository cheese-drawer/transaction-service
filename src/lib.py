"""Very contrived example of an application's business logic.

Intended to show how you should define all of your logic separately,
then import the classes, methods, & constants you need into the
routes defined at `./app/src/main.py`.
"""
import asyncio
import random


def do_a_quick_thing() -> int:
    """Contrived example method: get a random int from 0 to 100."""
    return random.randint(0, 100)


async def do_a_long_thing() -> str:
    """Contrived example method number 2, simulates a long running method.

    Returns a string that never changes.
    """
    await asyncio.sleep(1)

    return 'that took forever'
