"""Tests for all util functions."""
from itertools import tee
from pathlib import Path
from typing import cast
import unittest
import logging
import importlib

import algobattle
from algobattle.util import Table, import_problem_from_path
from algobattle.docker import measure_runtime_overhead

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    @classmethod
    def setUpClass(cls) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        cls.problem = Problem.Problem()
        cls.config = Path(algobattle.__file__).resolve().parent / 'config' / 'config.ini'
        cls.tests_path = Path(cast(str, Problem.__file__)).parent

    def test_import_problem_from_path(self):
        self.assertIsNotNone(import_problem_from_path(self.tests_path))
        self.assertRaises(ValueError, lambda: import_problem_from_path(Path("foo")))

    def test_measure_runtime_overhead(self):
        self.assertGreater(measure_runtime_overhead(), 0)


class TableTests(unittest.TestCase):
    """Tests for the Table formatting."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lists = [["frst", "second column", "C"], [2, 3, 4], [1.111111111, None, "9"]]
        cls.table = Table.from_lists(cls.lists)

    def check_basic_format(self, formatted: str, width: int = 10000, height: int = 10000):
        lines = formatted.split("\n")
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
        formatted = format(self.table, "38")
        self.check_basic_format(formatted, 38)

    def test_width_slightly_small(self):
        formatted = format(self.table, "37")
        self.check_basic_format(formatted, 37)

    def test_width_cutoff(self):
        formatted = format(self.table, "30")
        self.lists = [row[:-1] for row in self.lists]
        self.check_basic_format(formatted, 30)

    def test_height_slightly_small(self):
        formatted = format(self.table, "10000, 6")
        self.check_basic_format(formatted, 100000, 6)

    def test_height_smaller(self):
        formatted = format(self.table, "10000, 5")
        self.check_basic_format(formatted, 10000, 5)

    def test_height_very_small(self):
        formatted = format(self.table, "10000, 3")
        self.check_basic_format(formatted, 10000, 3)

    def test_height_cutoff(self):
        formatted = format(self.table, "10000, 2")
        self.lists = self.lists[:2]
        self.check_basic_format(formatted, 10000, 2)


if __name__ == '__main__':
    unittest.main()
