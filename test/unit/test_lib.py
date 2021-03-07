"""Tests for src/lib.py"""
# pylint: disable=missing-function-docstring


import unittest
from unittest import TestCase

from src import lib

from helpers import async_test


class TestDoAQuickThing(TestCase):
    """Tests for method do_a_quick_thing."""

    def test_wont_return_an_int_less_than_0(self) -> None:
        result = lib.do_a_quick_thing()

        self.assertGreaterEqual(result, 0)

    def test_wont_return_an_int_over_100(self) -> None:
        result = lib.do_a_quick_thing()

        self.assertLessEqual(result, 100)


class TestDoALongThing(TestCase):
    """Tests for method do_a_long_thing."""

    @async_test
    async def test_returns_string_that_took_forever(self) -> None:
        result = await lib.do_a_long_thing()

        self.assertEqual(result, 'that took forever')


if __name__ == '__main__':
    unittest.main()
