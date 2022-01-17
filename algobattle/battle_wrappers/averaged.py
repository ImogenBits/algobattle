"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

import logging

from algobattle.battle_wrapper import BattleWrapper

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def wrapper(self, match, options: dict = {}) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it by
        calls to the match.update_match_data function.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        options: dict
            No additional options are used for this wrapper.
        """
        approximation_ratios = []
        logger.info('==================== Averaged Battle, Instance Size: {}, Rounds: {} ===================='
                    .format(match.match_data['approx_inst_size'], match.match_data['approx_iters']))
        for i in range(match.match_data['approx_iters']):
            logger.info('=============== Iteration: {}/{} ==============='.format(i + 1, match.match_data['approx_iters']))
            approx_ratio = match._one_fight(instance_size=match.match_data['approx_inst_size'])
            approximation_ratios.append(approx_ratio)

            curr_pair = match.match_data['curr_pair']
            curr_round = match.match_data[curr_pair]['curr_round']
            match.update_match_data({curr_pair: {curr_round: {'approx_ratios':
                                    match.match_data[curr_pair][curr_round]['approx_ratios'] + [approx_ratio]}}})

    def format_as_utf8(self, match_data: dict) -> str:
        """Format the provided match_data for averaged battles.

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
        formatted_output_string += 'Battle Type: Averaged Battle\n\r'
        formatted_output_string += '╔═════════╦═════════╦' \
                                   + ''.join(['══════╦' for i in range(match_data['rounds'])]) \
                                   + '══════╦══════╦════════╗' + '\n\r' \
                                   + '║   GEN   ║   SOL   ' \
                                   + ''.join(['║{:^6s}'.format('R' + str(i + 1)) for i in range(match_data['rounds'])]) \
                                   + '║ LAST ║ SIZE ║  ITER  ║' + '\n\r' \
                                   + '╟─────────╫─────────╫' \
                                   + ''.join(['──────╫' for i in range(match_data['rounds'])]) \
                                   + '──────╫──────╫────────╢' + '\n\r'

        for pair in match_data.keys():
            if isinstance(pair, tuple):

                avg = [0.0 for i in range(match_data['rounds'])]

                for i in range(match_data['rounds']):
                    executed_iters = len(match_data[pair][i]['approx_ratios'])
                    n_dead_iters = executed_iters - len([i for i in match_data[pair][i]['approx_ratios'] if i != 0.0])

                    if executed_iters - n_dead_iters > 0:
                        avg[i] = sum(match_data[pair][i]['approx_ratios']) // (executed_iters - n_dead_iters)

                curr_round = match_data[pair]['curr_round']
                curr_iter = len(match_data[pair][curr_round]['approx_ratios'])
                latest_approx_ratio = 0.0
                if match_data[pair][curr_round]['approx_ratios']:
                    latest_approx_ratio = match_data[pair][curr_round]['approx_ratios'][-1]

                formatted_output_string += '║{:>9s}║{:>9s}'.format(pair[0], pair[1]) \
                                           + ''.join(['║{:>6.2f}'.format(avg[i]) for i in range(match_data['rounds'])]) \
                                           + '║{:>6.2f}║{:>6d}║{:>3d}/{:>3d} ║'.format(latest_approx_ratio,
                                                                                       match_data['approx_inst_size'],
                                                                                       curr_iter,
                                                                                       match_data['approx_iters']) + '\r'
        formatted_output_string += '\n╚═════════╩═════════╩' \
                                   + ''.join(['══════╩' for i in range(match_data['rounds'])]) \
                                   + '══════╩══════╩════════╝' + '\n\r'

        return formatted_output_string
