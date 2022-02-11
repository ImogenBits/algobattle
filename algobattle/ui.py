"""UI class, responsible for printing nicely formatted output to STDOUT."""
import curses
import logging
import sys
from typing import Callable

from algobattle.observer import Observer
from algobattle.match import Match
from algobattle import __version__ as version

logger = logging.getLogger('algobattle.ui')


class Ui(Observer):
    """The UI Class declares methods to output information to STDOUT."""

    @staticmethod
    def check_for_terminal(function: Callable) -> Callable:
        """Ensure that we are attached to a terminal."""
        def wrapper(self, *args, **kwargs):
            if not sys.stdout.isatty():
                logger.error('Not attached to a terminal.')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    @check_for_terminal
    def __init__(self) -> None:
        if sys.stdout.isatty():
            self.stdscr = curses.initscr()  # type: ignore
            curses.cbreak()                 # type: ignore
            curses.noecho()                 # type: ignore
            self.stdscr.keypad(1)

    @check_for_terminal
    def restore(self) -> None:
        """Restore the console. This will be later moved into a proper deconstruction method."""
        if sys.stdout.isatty():
            curses.nocbreak()               # type: ignore
            self.stdscr.keypad(0)
            curses.echo()                   # type: ignore
            curses.endwin()                 # type: ignore

    @check_for_terminal
    def update(self, match: Match) -> None:
        """Receive updates by observing the match object and prints them out formatted.

        Parameters
        ----------
        match : dict
            The observed match object.
        """
        self.stdscr.refresh()
        self.stdscr.clear()
        self.print_formatted_data_to_stdout(match)  # TODO: Refactor s.t. the output stream can be chosen by the user.

    def print_formatted_data_to_stdout(self, match: Match) -> None:
        """Output the formatted match data of a battle wrapper to stdout.

        Parameters
        ----------
        match : Match
            Match object containing match data generated by match.run().
        """
        out = r'              _    _             _           _   _   _       ' + '\n\r' \
              + r'             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ' + '\n\r' \
              + r'            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ' + '\n\r' \
              + r'           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ' + '\n\r' \
              + r'          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ' + '\n\r' \
              + r'                      |___/                                  ' + '\n\r'

        out += '\nAlgobattle version {}\n\r'.format(version)

        print(out + match.format_as_utf8())