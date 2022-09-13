"""Abstract base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from __future__ import annotations
import logging
from abc import abstractmethod, ABC
from typing import Callable, List, Tuple
from importlib import import_module
from configparser import ConfigParser

from algobattle.fight_handler import FightHandler
from algobattle.observer import Observer
from algobattle.subject import Subject
from algobattle.team import Matchup

logger = logging.getLogger('algobattle.battle_wrapper')


class BattleWrapper(ABC, Subject):
    """Abstract Base class for wrappers that execute a specific kind of battle."""

    _observers: List[Observer] = []

    @staticmethod
    def initialize(wrapper_name: str, config: ConfigParser) -> BattleWrapper:
        """Try to import and initialize a Battle Wrapper from a given name.

        For this to work, a BattleWrapper module with the same name as the argument
        needs to be present in the algobattle/battle_wrappers folder.

        Parameters
        ----------
        wrapper : str
            Name of a battle wrapper module in algobattle/battle_wrappers.

        config : ConfigParser
            A ConfigParser object containing possible additional arguments for the battle_wrapper.

        Returns
        -------
        BattleWrapper
            A BattleWrapper object of the given wrapper_name.

        Raises
        ------
        ValueError
            If the wrapper does not exist in the battle_wrappers folder.
        """
        try:
            wrapper_module = import_module("algobattle.battle_wrappers." + wrapper_name)
            return getattr(wrapper_module, wrapper_name.capitalize())(config)
        except ImportError as e:
            logger.critical(f"Importing a wrapper from the given path failed with the following exception: {e}")
            raise ValueError from e

    @abstractmethod
    def reset_round_data(self) -> None:
        """Resets the round_data dict to default values."""
        raise NotImplementedError

    @staticmethod
    def reset_state(function: Callable) -> Callable:
        """Wrapper that resets the state of a round."""
        def wrapper(self, *args, **kwargs):
            self.reset_round_data()
            return function(self, *args, **kwargs)
        return wrapper

    @abstractmethod
    def run_round(self, fight_handler: FightHandler, matchup: Matchup) -> None:
        """Execute a full round of fights between two teams configured in the fight_handler.

        During execution, the concrete BattleWrapper should update the round_data dict
        to which Observers can subscribe in order to react to new intermediate results.

        Parameters
        ----------
        fight_handler: FightHandler
            A FightHandler object that manages solving and generating teams as well
            single fights between them.
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_valuations(self, round_data0: dict, round_data1: dict) -> Tuple:
        """Return a pair of valuations that help to calculate points.

        In order to evaluate how the results of two teams that
        fought against one another can be judged, the battle wrapper
        should give each team some score depending on their performance
        relative to the other team. A higher score means a better performance.

        round_data0: dict
            round_data in which the 0th team solved instances.
        round_data1: dict
            round_data in which the 1st team solved instances.
        """
        raise NotImplementedError

    def format_round_contents(self, round_data: dict) -> str:
        """Format the provided round_data for a round entry in a formatted output.

        The string length should not exceed 9 characters.
        """
        return "???"

    def format_misc_contents(self, round_data: dict) -> Tuple:
        """Format additional data that is to be displayed.

        Make sure that the number of elements of the returned tuple match
        up with the number of elements returned by format_misc_headers.

        The string length should not exceed 9 characters.
        """
        return None

    def format_misc_headers(self) -> Tuple:
        """Return which strings are to be used as headers a formatted output.

        Make sure that the number of elements of the returned tuple match
        up with the number of elements returned by format_misc_contents.

        The string length should not exceed 9 characters.
        """
        return None

    def format_as_utf8(self, match_data: dict) -> str:
        """Format the match_data for the battle wrapper as a UTF-8 string.

        The output should not exceed 80 characters, assuming the default
        of a battle of 5 rounds.

        Parameters
        ----------
        match_data : dict
            dict containing match data generated by match.run().

        Returns
        -------
        str
            A formatted string on the basis of the match_data.
        """
        formatted_output_string = ""

        formatted_output_string += 'Battles of type {} are currently not compatible with the ui.'.format(match_data['type'])
        formatted_output_string += 'Here is a dump of the match_data dict anyway:\n{}'.format(match_data)

        return formatted_output_string

    def attach(self, observer: Observer) -> None:
        """Subscribe a new Observer by adding them to the list of observers."""
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Unsubscribe an Observer by removing them from the list of observers."""
        self._observers.remove(observer)

    def notify(self) -> None:
        """Notify all subscribed Observers by calling their update() functions."""
        for observer in self._observers:
            observer.update(self)
