"""Tests for the terminal ui."""
from unittest import TestCase
from itertools import tee

from algobattle.util import Table
from algobattle.ui import _format_table, _format_obj


class TableTests(TestCase):
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



class UiTests(TestCase):
    """Tests for other ui module functions."""

    def test_format_obj_table(self):
        table = Table.from_lists([["frst", "second column", "C"], [2, 3, 4], [1.111111111, None, "9"]])
        self.assertEqual(_format_obj(table), _format_table(table, 10000, 10000))

    def test_format_obj_mapping(self):
        mapping = {1: "one", 2: "two", 3: "three" * 50}
        mapping_formatted = _format_obj(mapping, 20, 5)
        for line in mapping_formatted:
            self.assertLessEqual(len(line), 50)
        self.assertEqual(len(mapping_formatted), 5)
        self.assertEqual(mapping_formatted[3][:7], " " * 7)

    def test_format_obj_string(self):
        string_formatted = _format_obj("test" * 50, 16, 5)
        self.assertEqual(string_formatted, ["test" * 4] * 5)

    def test_format_obj_none(self):
        self.assertEqual(_format_obj(None), [])