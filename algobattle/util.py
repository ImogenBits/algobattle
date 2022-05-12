"""Collection of utility functions."""
from __future__ import annotations
import logging
import importlib.util
from pathlib import Path
from sys import modules
from typing import Any, Iterable, Iterator, Sequence, TypeVar
from inspect import getmembers, isclass
from argparse import Action, SUPPRESS

from algobattle.problem import Problem

logger = logging.getLogger("algobattle.util")


def get_matching_file(path: Path, *files: str) -> Path:
    """Searches the file structure for the first file found in the targeted directory.

    Parameters
    ----------
    path : Path
        Path to a directory or file, if it's a file the path will be returned unaltered.

    Returns
    -------
    Path
        Path to the first found file or the parent directory if it contains no matching files.

    Raises
    ------
    RuntimeError
        If the path doesn't exist in the file system.
    ValueError
        If the targeted directory contains no matching files.
    """
    if not path.exists():
        raise RuntimeError
    elif path.is_dir():
        for ending in files:
            if (path / ending).is_file():
                return path / ending
        raise ValueError
    else:
        return path


def import_problem_from_path(path: Path) -> Problem:
    """Try to import and initialize a Problem object from a given path.

    Parameters
    ----------
    path : Path
        Path in the file system to a problem folder.

    Returns
    -------
    Problem
        Returns an object of the problem.

    Raises
    ------
    ValueError
        If the given path does not point to a valid Problem.
    RuntimeError
        If some unexpected error occurs while importing the Problem.
    """
    try:
        path = get_matching_file(path.resolve(), "__init__.py", "problem.py")
    except RuntimeError:
        logger.warning(f"Problem path '{path}' does not exist in the file system!")
        raise ValueError
    except ValueError:
        logger.warning(f"Problem path '{path}' points to a directory that doesn't contain a Problem.")
        raise ValueError

    try:
        spec = importlib.util.spec_from_file_location("problem", path)
        assert spec is not None
        assert spec.loader is not None
        problem_module = importlib.util.module_from_spec(spec)
        modules[spec.name] = problem_module
        spec.loader.exec_module(problem_module)

    except Exception as e:
        logger.critical(f'Importing the given problem failed with the following exception: "{e}"')
        raise RuntimeError

    potential_problems = []
    for _, obj in getmembers(problem_module):
        # issubclass won't work here til 3.11
        if isclass(obj) and Problem in obj.__bases__:
            potential_problems.append(obj)

    if len(potential_problems) == 0:
        logger.warning(f"Problem path '{path}' points to a module that doesn't contain a Problem.")
        raise ValueError
    if len(potential_problems) > 1:
        formatted_list = ", ".join(f"'{p.name}'" for p in potential_problems)
        logger.warning(f"Problem path '{path}' points to a module containing more than one Problem: {formatted_list}")
        raise ValueError

    return potential_problems[0]()


T = TypeVar("T")


def intersperse(elem: T, iterable: Iterable[T]) -> Iterator[T]:
    """Inserts `elem` between each element of `iterable`."""
    it = iter(iterable)
    yield next(it)
    for e in it:
        yield elem
        yield e


class Table:
    """Stores data in a 2D table."""

    def __init__(self, column_names: list[str], num_header_cols: int = 0) -> None:
        if num_header_cols > len(column_names):
            raise ValueError
        self.num_header_cols = num_header_cols
        self.column_names = column_names[:]
        self._data: list[list[Any]] = []

    def add_row(self, row: Sequence) -> None:
        """Adds a new row to the table. Raises `ValueError` if it has an incompatible length."""
        if len(row) != len(self.column_names):
            raise ValueError
        self._data.append(list(row))

    @classmethod
    def from_lists(cls, data: list[list[Any]], num_header_cols: int = 0) -> Table:
        """Creates a table from a 2D array."""
        if not data:
            raise ValueError
        table = cls(data[0], num_header_cols)
        for row in data[1:]:
            table.add_row(row)
        return table

    @property
    def num_rows(self) -> int:
        """Number of rows in the table excluding the header."""
        return len(self._data)

    @property
    def num_cols(self) -> int:
        """Number of columns in the table."""
        return len(self.column_names)

    def __getitem__(self, key: tuple[int, int]) -> Any:
        row, col = key
        if row >= self.num_rows or col >= self.num_cols:
            raise IndexError
        return self._data[row][col]

    def __setitem__(self, key: tuple[int, int], val: Any) -> None:
        row, col = key
        if row >= self.num_rows or col >= self.num_cols:
            raise IndexError
        self._data[row][col] = val


# this should probably be done with a library
# (well really this should probably not be done at all but its cute)
def parse_doc_for_param(doc: str, name: str) -> str:
    """Parses a docstring to find the documentation of a single parameter.

    Parameters
    ----------
    doc : str
        The docstring that will be parsed.
    name
        The name of the parameter.

    Returns
    -------
    str
        The documentation of that parameter.

    Raises
    ------
    ValueError
        If the parameter doesn't exist.
    """
    lines = doc.split("\n")
    try:
        start = next(i for i, line in enumerate(lines) if line.find(name) == 0)
    except StopIteration:
        raise ValueError

    param_doc = []
    for line in lines[start + 1 :]:
        if not line.startswith(" "):
            break
        param_doc.append(line.strip())

    return " ".join(param_doc)


class NestedHelp(Action):
    """Argparse action to generate nested help messages."""

    def __init__(self, option_strings, dest=SUPPRESS, default=SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs="?", help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        """Prints the help message to the console and then exits the parser immedietly."""
        formatter = parser._get_formatter()

        # usage
        formatter.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)

        # description
        formatter.add_text(parser.description)

        # positionals, optionals and user-defined groups
        for action_group in parser._action_groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        if isinstance(values, str):
            battle_group = next(g for g in parser._action_groups if g.title == "battle arguments")
            arg_groups = {g.title: g for g in battle_group._action_groups}
            groups = []
            if values == "all":
                groups = battle_group._action_groups
            elif values in arg_groups:
                groups = [arg_groups[values]]

            for action_group in groups:
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(action_group._group_actions)
                formatter.end_section()

        # epilog
        formatter.add_text(parser.epilog)

        # determine help from format above
        print(formatter.format_help())
        parser.exit()


T = TypeVar("T")


def inherit_docs(obj: T) -> T:
    """Decorator to mark a method as inheriting its docstring.

    Python 3.5+ already does this, but pydocstyle needs a static hint.
    """
    return obj


def wrap_text(text: str, width: int, indent: str = "") -> str:
    """Wraps the text with line breaks to be at most `width` wide indenting each line beyond the first with `indent`."""
    out = text[:width]
    for i in range(width, len(text), width - len(indent)):
        out += f"\n{indent}{text[i : i + width - len(indent)]}"
    return out


def replace_nth(string: str, substr: str, replace: str, n: int) -> str:
    """Replaces the `n`th occurence of `substr` in `string` with `replace`."""
    pos = -1
    for _ in range(n):
        new_pos = string.find(substr, pos + 1)
        if new_pos == -1:
            break
        pos = new_pos
    if pos == -1:
        return string
    else:
        before = string[:pos]
        after = string[pos + len(substr) :]
        return before + replace + after
