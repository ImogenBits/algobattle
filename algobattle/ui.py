"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from logging.handlers import MemoryHandler
from math import ceil
from sys import stdout
from typing import Any, Callable, Mapping, TypeVar
from collections import deque

from algobattle.events import SharedData, SharedObserver, Subject
from algobattle.util import Table, inherit_docs, intersperse, wrap_text


logger = logging.getLogger("algobattle.ui")

F = TypeVar("F", bound=Callable)


def check_for_terminal(function: F) -> F:
    """Ensure that we are attached to a terminal."""

    def wrapper(self, *args, **kwargs):
        if not stdout.isatty():
            logger.error("Not attached to a terminal.")
            return None
        else:
            return function(self, *args, **kwargs)

    return wrapper  # type: ignore


def _format_table(table: Table, max_width: int, max_height: int) -> list[str]:
    """Formats the table into a multiline string."""
    data = [[str(e) for e in row] for row in table._data]

    # calculating how much vertical space we need, if the full table is too high we first drop the lines between data
    # entries, if it still is too high then the outer border, then the line between the column names and data.
    # should we then still not have enough space we have to truncate the data.
    max_height = max(table.num_rows + 1, max_height)
    horizontal_data_seps = 4 + table.num_rows + (table.num_rows - 1) <= max_height
    border = 4 + table.num_rows <= max_height
    horizontal_header_sep = 2 + table.num_rows <= max_height

    # similar process for horizontal space. here the only unnessecary space is the blank space around the seperating
    # lines, so if that isn't enough we have to drop data right away.
    # the columns will all be the width of its longest entry, but data columns are at least 5 wide.
    # this gives us enough space to always format and align the results nicely.
    col_widths = [max(len(row[i]) for row in [table.column_names, *data]) for i in range(table.num_cols)]
    for i in range(table.num_header_cols, table.num_cols):
        col_widths[i] = max(5, col_widths[i])
    if sum(col_widths) + 3 * (len(col_widths) - 1) + (4 if border else 0) <= max_width:
        vertical_sep_width = 3
    else:
        vertical_sep_width = 1
    # the first col doesn't add one normal sep but the two ending ones, which are one longer in total
    used_width = 1
    num_cols = len(col_widths)
    for i, width in enumerate(col_widths):
        used_width += width + vertical_sep_width
        if used_width > max_width:
            num_cols = i
            break

    data = [row[:num_cols] for row in data]
    col_widths = col_widths[:num_cols]

    # we can now create format strings that specifiy the overall shape of each row. they will look something like this:
    # {start}{sep}{data}{middle}{data}{middle}{middle}{end}
    # or
    # {start}{sep}{sep}{sep}{middle}{sep}{sep}{sep}{end}
    # for a data and seperator row respectively.
    border_sep_padding = "{sep}" * (vertical_sep_width // 2)
    vertical_sep_fmt = border_sep_padding + "{middle}" + border_sep_padding
    horizontal_sep_fmt = vertical_sep_fmt.join("{sep}" * width for width in col_widths)
    data_fmt = vertical_sep_fmt.join(f"{{: ^{width}}}" for width in col_widths)
    if border:
        horizontal_sep_fmt = "{start}" + border_sep_padding + horizontal_sep_fmt + border_sep_padding + "{end}"
        data_fmt = "{start}" + border_sep_padding + data_fmt + border_sep_padding + "{end}"

    # each format string can now be interpolated. the different kinds of seperators are used to get the right shape of
    # ASCII line art so that they all connect nicely. start, middle, and end are for pipe like characters that have the
    # right connection to their surroundings, sep is the filler character used to make long horizontal lines
    out = []
    out.append(data_fmt.format(*table.column_names, start="║", middle="║", end="║", sep=" "))
    if horizontal_header_sep:
        out.append(horizontal_sep_fmt.format(start="╟", middle="╫", end="╢", sep="─"))
    data = [data_fmt.format(*row, start="║", middle="║", end="║", sep=" ") for row in data]
    if horizontal_data_seps:
        data = intersperse(horizontal_sep_fmt.format(start="╟", middle="╫", end="╢", sep="─"), data)
    out += data
    if border:
        out.insert(0, horizontal_sep_fmt.format(start="╔", middle="╦", end="╗", sep="═"))
        out.append(horizontal_sep_fmt.format(start="╚", middle="╩", end="╝", sep="═"))

    return out


def _format_obj(obj: SharedData, max_width: int = 10000, max_height: int = 10000) -> list[str]:
    if isinstance(obj, Table):
        return _format_table(obj, max_width, max_height)
    elif isinstance(obj, Mapping):
        return [wrap_text(f"{key}: {val}", max_width, " " * (len(key) + 2)) for key, val in obj.items()]
    elif isinstance(obj, str):
        out = [wrap_text(line, max_width).split("\n") for line in obj.split("\n")]
        return [line for sublist in out for line in sublist]
    elif obj is None:
        return []


class Ui(SharedObserver):
    """The UI Class declares methods to output information to STDOUT."""

    @check_for_terminal
    def __init__(self, logger: logging.Logger, logging_level: int = logging.NOTSET, num_records: int = 10) -> None:
        super().__init__()
        if stdout.isatty():
            self.stdscr = curses.initscr()  # type: ignore
            curses.cbreak()  # type: ignore
            curses.noecho()  # type: ignore
            self.stdscr.keypad(True)
            handler = BufferHandler(self, logging_level, num_records)
            logger.addHandler(handler)
            self.sections: dict[str, SharedData] = {
                "systeminfo": None,
                "match": None,
                "battle": None,
                "fight": None,
                "logs": None,
            }

    @check_for_terminal
    def restore(self) -> None:
        """Restore the console. This will be later moved into a proper deconstruction method."""
        if stdout.isatty():
            curses.nocbreak()  # type: ignore
            self.stdscr.keypad(False)
            curses.echo()  # type: ignore
            curses.endwin()  # type: ignore

    @check_for_terminal
    def update(self, section: str, data: SharedData) -> None:
        """Updates the specified section of the UI."""
        if section not in self.sections:
            return
        self.sections[section] = data
        rows, cols = self.stdscr.getmaxyx()
        cols -= 1
        formatted: dict[str, list[str]] = {section: [] for section in self.sections}

        for section in ("systeminfo", "battle", "fight"):
            formatted[section] = _format_obj(self.sections[section], max_width=cols)

        logs = _format_obj(self.sections["logs"], max_width=cols - 2)
        formatted["logs"] = (
            ["╔" + " logs ".center(cols - 2, "═") + "╗"]
            + ["║" + line + " " * (cols - 2 - len(line)) + "║" for line in logs]
            + ["╚" + "═" * (cols - 2) + "╝"]
        )

        free_space = rows - sum(len(i) for i in formatted.values()) - sum(1 for s in formatted.values() if s != [])
        formatted["match"] = _format_obj(self.sections["match"], cols, free_space)

        out = []
        for val in formatted.values():
            if val:
                out += val + [""]
        out = out[:-1]

        if len(out) + 6 <= rows and 52 <= cols:
            logo = [
                r"     _    _             _           _   _   _       ",
                r"    / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ",
                r"   / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ",
                r"  / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ",
                r" /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ",
                r"             |___/                                  ",
            ]
            out = [line.center(cols) for line in logo] + out
        elif len(out) + 1 <= rows and 10 <= cols:
            out = ["Algobattle".center(cols)] + out
        else:
            out = out[:rows]

        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "\n".join(out))
        self.stdscr.refresh()
        self.stdscr.nodelay(1)
        c = self.stdscr.getch()
        if c == 3:
            raise KeyboardInterrupt
        else:
            curses.flushinp()  # type: ignore


class BufferHandler(MemoryHandler, Subject):
    """Logging handler that buffers the last few messages."""

    default_event = "logs"

    def __init__(self, ui: Ui, level: int, num_records: int):
        super().__init__(num_records)
        Subject.__init__(self)
        self._buffer = deque(maxlen=num_records)
        self.attach(ui)

    @inherit_docs
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._buffer.append(msg)
            self.notify("\n".join(self._buffer))

        except Exception:
            self.handleError(record)
