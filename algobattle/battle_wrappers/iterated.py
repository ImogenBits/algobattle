"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""

import logging

from algobattle.battle_wrapper import BattleWrapper

logger = logging.getLogger('algobattle.battle_wrappers.iterated')


class Iterated(BattleWrapper):
    """Class of an iterated battle Wrapper."""

    def wrapper(self, match, options: dict = {'exponent': 2}) -> None:
        """Execute one iterative battle between a generating and a solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the power of iterations since the last unsolvable instance to the
        given exponent.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the first
        value that an algorithm has failed on.

        The wrapper automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached.

        During execution, this function updates the match_data of the match
        object which is passed to it by
        calls to the match.update_match_data function.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        options: dict
            A dict that contains an 'exponent' key with an int value of at least 1,
            which determines the step size increase.
        """
        curr_pair = match.match_data['curr_pair']
        curr_round = match.match_data[curr_pair]['curr_round']

        n = match.problem.n_start
        maximum_reached_n = 0
        i = 0
        exponent = options['exponent']
        n_max = n_cap = match.match_data[curr_pair][curr_round]['cap']
        alive = True

        logger.info('==================== Iterative Battle, Instanze Size Cap: {} ===================='.format(n_cap))
        while alive:
            logger.info('=============== Instance Size: {}/{} ==============='.format(n, n_cap))
            approx_ratio = match._one_fight(instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > match.approximation_ratio:
                logger.info('Solver {} does not meet the required solution quality at instance size {}. ({}/{})'
                            .format(match.solving_team, n, approx_ratio, match.approximation_ratio))
                alive = False

            if not alive and i > 1:
                # The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info('Setting the solution cap to {}...'.format(n))
                n_cap = n
                n -= i ** exponent
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                # We solved an instance of bigger size than before
                maximum_reached_n = n

            if n + 1 == n_cap:
                alive = False
            else:
                i += 1
                n += i ** exponent

                if n >= n_cap and n_cap != n_max:
                    # We have failed at this value of n already, reset the step size!
                    n -= i ** exponent - 1
                    i = 1
                elif n >= n_cap and n_cap == n_max:
                    logger.info('Solver {} exceeded the instance size cap of {}!'.format(match.solving_team, n_max))
                    maximum_reached_n = n_max
                    alive = False

            match.update_match_data({curr_pair: {curr_round: {'cap': n_cap, 'solved': maximum_reached_n, 'attempting': n}}})
