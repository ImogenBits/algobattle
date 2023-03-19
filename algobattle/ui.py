"""UI class, responsible for printing nicely formatted output to STDOUT."""
import curses
import logging
from sys import stdout
from typing import Callable, ParamSpec, TypeVar
from importlib.metadata import version as pkg_version

from prettytable import PrettyTable, DOUBLE_BORDER

from algobattle.match import Match

logger = logging.getLogger("algobattle.ui")


P = ParamSpec("P")
R = TypeVar("R")


def check_for_terminal(function: Callable[P, R]) -> Callable[P, R | None]:
    """Ensure that we are attached to a terminal."""

    def wrapper(*args: P.args, **kwargs: P.kwargs):
        if not stdout.isatty():
            logger.error("Not attached to a terminal.")
            return None
        else:
            return function(*args, **kwargs)

    return wrapper


def display_match(match: Match) -> str:
    """Formats the match data into a table that can be printed to the terminal."""
    table = PrettyTable(field_names=["Generator", "Solver", "Result"], min_width=5)
    table.set_style(DOUBLE_BORDER)
    table.align["Result"] = "r"

    for matchup, result in match.results.items():
        table.add_row([str(matchup.generator), str(matchup.solver), result.format_score(result.score())])

    return f"Battle Type: {match.config.battle_type.name()}\n{table}"


class Ui:
    """The UI Class declares methods to output information to STDOUT."""

    @check_for_terminal
    def __init__(self) -> None:
        super().__init__()
        self.stdscr = curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)

    def __enter__(self) -> "Ui":
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    @check_for_terminal
    def close(self) -> None:
        """Restore the console."""
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    @check_for_terminal
    def update(self, match: Match) -> None:
        """Disaplys the current status of the match to the cli."""
        match_display = display_match(match)
        battle_display = ""

        out = [
            r"              _    _             _           _   _   _       ",
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ",
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ",
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ",
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ",
            r"                      |___/                                  ",
            f"Algobattle version {pkg_version(__package__)}",
            match_display,
            "",
            battle_display,
        ]

        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "\n".join(out))
        self.stdscr.refresh()
        self.stdscr.nodelay(True)

        # on windows curses swallows the ctrl+C event, we need to manually check for the control sequence
        # ideally we'd be doing this from inside the docker image run wait loop too
        c = self.stdscr.getch()
        if c == 3:
            raise KeyboardInterrupt
        else:
            curses.flushinp()
