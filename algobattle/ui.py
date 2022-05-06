"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from logging.handlers import MemoryHandler
from sys import stdout
from typing import Any, Callable, TypeVar
from collections import deque

from algobattle import __version__ as version
from algobattle.events import SharedObserver, Subject
from algobattle.match import MatchResult
from algobattle.util import inherit_docs


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


class Ui(SharedObserver):
    """The UI Class declares methods to output information to STDOUT."""

    titles = {
        "match": "",
        "battle": "Current battle info:\n",
    }

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
            self.sections: dict[str, Any] = {
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
    def update(self, section: str, data: Any) -> None:
        """Updates the specified section of the UI."""
        if section not in self.sections:
            return
        self.sections[section] = data
        rows, cols = self.stdscr.getmaxyx()
        cols -= 1
        formatted: dict[str, list[str]] = {section: [] for section in self.sections}

        if self.sections["systeminfo"] is not None:
            formatted["systeminfo"] = [str(self.sections["systeminfo"]), ""]

        if self.sections["battle"] is not None:
            formatted["battle"] = self.sections["battle"].split("\n") + [""]

        if self.sections["fight"] is not None:
            formatted["fight"] = [f"{key}: {val}" for key, val in self.sections["fight"].items()] + [""]

        if self.sections["logs"] is not None:
            formatted["logs"] = ["-" * cols] + [line[:cols] for line in self.sections["logs"].split("\n")] + ["-" * cols]

        if self.sections["match"] is not None:
            free_space = rows - sum(len(i) for i in formatted.values())
            formatted["match"] = self.sections["match"].format(cols, free_space).split("\n") + [""]

        out = [line for section in formatted.values() for line in section][:rows]

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
