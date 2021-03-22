"""Extending unittest.TestCase to enforce a run time limit per test."""
# pylint: disable=missing-function-docstring

from typing import Any
import signal
from unittest import TestCase


class TestTimeoutException(Exception):
    """Indicate a test timed out."""


class TimeLimitedTestCase(TestCase):
    """
    TestCase with a setUp method limiting each test's run time.

    Uses global constant TEST_TIME_LIMIT to determine maximum run time,
    or defaults to 5 seconds.
    """

    TEST_TIME_LIMIT: int

    def _handle_timeout(self, _: Any, __: Any) -> None:
        raise TestTimeoutException(self.error_message)

    def setUp(self) -> None:
        try:
            seconds = self.TEST_TIME_LIMIT
        except AttributeError:
            seconds = 5

        self.seconds = seconds
        self.error_message = f'Test timed out after {seconds} seconds.'

        signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.alarm(self.seconds)

    def tearDown(self) -> None:
        signal.alarm(0)
