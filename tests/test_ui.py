"""Tests for the terminal ui."""
import unittest
from itertools import tee

from algobattle.util import Table
from algobattle.ui import _format_table


class TableTests(unittest.TestCase):
    """Tests for the Table formatting."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lists = [["frst", "second column", "C"], [2, 3, 4], [1.111111111, None, "9"]]
        cls.table = Table.from_lists(cls.lists)

    def check_basic_format(self, lines: list[str], width: int = 10000, height: int = 10000):
        formatted = "\n".join(lines)
        for line in lines:
            self.assertEqual(len(line), len(lines[0]))
        if len(lines) > 0:
            self.assertLessEqual(len(lines[0]), width)
            self.assertLessEqual(len(lines), height)
        first, second = tee(str(elem) for row in self.lists for elem in row)
        next(second, None)
        for e1, e2 in zip(first, second):
            self.assertLessEqual(formatted.find(e1), formatted.find(e2))

    def test_no_format_spec(self):
        formatted = _format_table(self.table, 38, 10000)
        self.check_basic_format(formatted, 38)

    def test_width_slightly_small(self):
        formatted = _format_table(self.table, 37, 10000)
        self.check_basic_format(formatted, 37)

    def test_width_cutoff(self):
        formatted = _format_table(self.table, 30, 10000)
        self.lists = [row[:-1] for row in self.lists]
        self.check_basic_format(formatted, 30)

    def test_height_slightly_small(self):
        formatted = _format_table(self.table, 10000, 6)
        self.check_basic_format(formatted, 100000, 6)

    def test_height_smaller(self):
        formatted = _format_table(self.table, 10000, 5)
        self.check_basic_format(formatted, 10000, 5)

    def test_height_very_small(self):
        formatted = _format_table(self.table, 10000, 3)
        self.check_basic_format(formatted, 10000, 3)
