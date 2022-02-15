"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

from __future__ import annotations
import itertools
import logging

import algobattle.battle_wrapper
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from algobattle.match import Match, MatchData

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(algobattle.battle_wrapper.BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def wrapper(self, match: Match, options: dict = {}) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        options: dict
            No additional options are used for this wrapper.
        """
        approximation_ratios = []
        logger.info('==================== Averaged Battle, Instance Size: {}, Rounds: {} ===================='
                    .format(match.match_data.approx_inst_size, match.match_data.approx_iters))
        for i in range(match.match_data.approx_iters):
            logger.info(f'=============== Iteration: {i + 1}/{match.match_data.approx_iters} ===============')
            approx_ratio = match._one_fight(instance_size=match.match_data.approx_inst_size)
            approximation_ratios.append(approx_ratio)

            curr_pair = match.match_data.curr_pair
            assert curr_pair is not None
            curr_round = match.match_data.pairs[curr_pair].curr_round
            match.match_data.pairs[curr_pair].rounds[curr_round].approx_ratios.append(approx_ratio)

    def calculate_points(self, match_data: MatchData, achievable_points: int) -> dict[str, float]:
        """Calculate the number of achieved points, given results.

        The valuation of an averaged battle is calculating by summing up
        the reciprocals of each solved fight. This sum is then divided by
        the total number of ratios to account for unsuccessful battles.

        Parameters
        ----------
        match_data : MatchData
            MatchData object containing the results of match.run().
        achievable_points : int
            Number of achievable points.

        Returns
        -------
        dict
            A mapping between team names and their achieved points.
            The format is {team_name: points [...]} for each
            team for which there is an entry in match_data and points is a
            float value. Returns an empty dict if no battle was fought.
        """
        points = dict()

        team_names: set[str] = set()
        for pair in match_data.pairs.keys():
            team_names = team_names.union(set(pair))
        team_combinations = itertools.combinations(team_names, 2)

        if len(team_names) == 1:
            return {team_names.pop(): achievable_points}

        if match_data.rounds <= 0:
            return {}
        points_per_round = round(achievable_points / match_data.rounds, 1)
        for pair in team_combinations:
            for i in range(match_data.rounds):
                points[pair[0]] = points.get(pair[0], 0)
                points[pair[1]] = points.get(pair[1], 0)

                ratios1 = match_data.pairs[pair].rounds[i].approx_ratios  # pair[1] was solver
                ratios0 = match_data.pairs[pair[::-1]].rounds[i].approx_ratios  # pair[0] was solver

                valuation0 = 0
                valuation1 = 0
                if ratios0 and sum(ratios0) != 0:
                    valuation0 = sum(1 / x if x != 0 else 0 for x in ratios0) / len(ratios0)
                if ratios1 and sum(ratios1) != 0:
                    valuation1 = sum(1 / x if x != 0 else 0 for x in ratios1) / len(ratios1)

                # Default values for proportions, assuming no team manages to solve anything
                points_proportion0 = 0.5
                points_proportion1 = 0.5

                # Normalize valuations
                if valuation0 + valuation1 > 0:
                    points_proportion0 = (valuation0 / (valuation0 + valuation1))
                    points_proportion1 = (valuation1 / (valuation0 + valuation1))

                points[pair[0]] += round(points_per_round * points_proportion0, 1)
                points[pair[1]] += round(points_per_round * points_proportion1, 1)

        return points

    def format_as_utf8(self, match_data: MatchData) -> str:
        """Format the provided match_data for averaged battles.

        Parameters
        ----------
        match_data : MatchData
            MatchData object containing match data generated by match.run().

        Returns
        -------
        str
            A formatted string on the basis of the match_data.
        """
        formatted_output_string = ""
        formatted_output_string += 'Battle Type: Averaged Battle\n\r'
        formatted_output_string += '╔═════════╦═════════╦' \
                                   + ''.join(['══════╦' for i in range(match_data.rounds)]) \
                                   + '══════╦══════╦════════╗' + '\n\r' \
                                   + '║   GEN   ║   SOL   ' \
                                   + ''.join([f'║{"R" + str(i + 1):^6s}' for i in range(match_data.rounds)]) \
                                   + '║ LAST ║ SIZE ║  ITER  ║' + '\n\r' \
                                   + '╟─────────╫─────────╫' \
                                   + ''.join(['──────╫' for i in range(match_data.rounds)]) \
                                   + '──────╫──────╫────────╢' + '\n\r'

        for pair in match_data.pairs.keys():
            avg = [0.0 for i in range(match_data.rounds)]

            for i in range(match_data.rounds):
                executed_iters = len(match_data.pairs[pair].rounds[i].approx_ratios)
                n_dead_iters = executed_iters - len([i for i in match_data.pairs[pair].rounds[i].approx_ratios if i != 0.0])

                if executed_iters - n_dead_iters > 0:
                    avg[i] = sum(match_data.pairs[pair].rounds[i].approx_ratios) / (executed_iters - n_dead_iters)

            curr_round = match_data.pairs[pair].curr_round
            curr_iter = len(match_data.pairs[pair].rounds[curr_round].approx_ratios)
            latest_approx_ratio = 0.0
            if match_data.pairs[pair].rounds[curr_round].approx_ratios:
                latest_approx_ratio = match_data.pairs[pair].rounds[curr_round].approx_ratios[-1]

            formatted_output_string += f'║{pair[0]:>9s}║{pair[1]:>9s}' \
                                        + ''.join([f'║{avg[1]:>6.2f}' for i in range(match_data.rounds)]) \
                                        + '║{:>6.2f}║{:>6d}║{:>3d}/{:>3d} ║'.format(latest_approx_ratio,
                                                                                    match_data.approx_inst_size,
                                                                                    curr_iter,
                                                                                    match_data.approx_iters) + '\r\n'
        formatted_output_string += '╚═════════╩═════════╩' \
                                   + ''.join(['══════╩' for i in range(match_data.rounds)]) \
                                   + '══════╩══════╩════════╝' + '\n\r'

        return formatted_output_string
