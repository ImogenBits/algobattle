"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
import sys
import os
import logging
import datetime as dt

from optparse import OptionParser
from pathlib import Path
from configparser import ConfigParser
from importlib.metadata import version as pkg_version

import algobattle
from algobattle.fight_handler import FightHandler
from algobattle.match import Match
from algobattle.team import Team
from algobattle.util import import_problem_from_path, initialize_wrapper
from algobattle.ui import Ui
from algobattle.docker_wrapper import DockerError


def setup_logging(logging_path: Path, verbose_logging: bool, silent: bool):
    """Creates and returns a parent logger.

    Parameters:
    ----------
    logging_path : Path
        Path to folder where the logfile should be stored at.
    verbose_logging : bool
        Flag indicating whether to include debug messages in the output
    silent : bool
        Flag indicating whether not to pipe the logging output to stderr.

    Returns:
    ----------
    Logger:
        The Logger object.
    """
    common_logging_level = logging.INFO

    if verbose_logging:
        common_logging_level = logging.DEBUG

    Path(logging_path).mkdir(exist_ok=True)

    _now = dt.datetime.now()

    time_seperator = ':' if os.name == 'posix' else '-'
    current_timestamp = '{:04d}-{:02d}-{:02d}_{:02d}{}{:02d}{}{:02d}'.format(_now.year, _now.month, _now.day, _now.hour, time_seperator, _now.minute, time_seperator, _now.second)
    logging_path = Path(logging_path, current_timestamp + '.log')

    logging.basicConfig(handlers=[logging.FileHandler(logging_path, 'w', 'utf-8')],
                        level=common_logging_level,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%H:%M:%S')

    logger = logging.getLogger('algobattle')

    if not silent:
        # Pipe logging out to console
        _consolehandler = logging.StreamHandler(stream=sys.stderr)
        _consolehandler.setLevel(common_logging_level)

        _consolehandler.setFormatter(logging.Formatter('%(message)s'))

        logger.addHandler(_consolehandler)

    logger.info('You can find the log files for this run in {}'.format(logging_path))
    return logger


def _exit_if_path_nonexistent(path: Path):
    """Check if a given path can be found in the os, exit otherwise.

    Parameters
    ----------
    path : Path
        The path to be checked for existence.
    """
    if not Path(path).exists():
        sys.exit('Path "{}" does not exist in the file system! Use "battle --help" for more information on usage and options.'.format(path))


def main():
    try:
        if len(sys.argv) < 2:
            sys.exit('Expecting (relative) path to the parent directory of a problem file as argument. Use "battle --help" for more information on usage and options.')

        problem_path = str(Path(sys.argv[1]).resolve())

        default_logging_path = Path(Path.home(), '.algobattle_logs')
        default_config_file = Path(Path(algobattle.__file__).parent, 'config', 'config.ini')

        # Option parser to process arguments from the console.
        usage = 'usage: %prog FILE [options]\nExpecting (relative) path to the directory of the problem as first argument.\nIf you provide generators, solvers and group numbers for multiple teams, make sure that the order is the same for all three arguments.'
        parser = OptionParser(usage=usage, version=pkg_version(__package__))
        parser.add_option('--verbose', dest='verbose_logging', action='store_true', help='Log all debug messages.')
        parser.add_option('--logging_path', dest='logging_path', default=default_logging_path, help='Specify the folder into which the log file is written to. Can either be a relative or absolute path to folder. If nonexisting, a new folder will be created. Default: ~/.algobattle_logs/')
        parser.add_option('--config_file', dest='config', default=default_config_file, help='Path to a .ini configuration file to be used for the run. Defaults to the packages config.ini')
        parser.add_option('--solvers', dest='solvers', default=str(Path(problem_path, 'solver')), help='Specify the folder names containing the solvers of all involved teams as a comma-seperated list. Default: arg1/solver/')
        parser.add_option('--generators', dest='generators', default=str(Path(problem_path, 'generator')), help='Specify the folder names containing the generators of all involved teams as a comma-seperated list. Default: arg1/generator/')
        parser.add_option('--team_names', dest='team_names', default='0', help='Specify the team names of all involved teams as a list strings as a comma-seperated list. Default: "0"')
        parser.add_option('--rounds', dest='battle_rounds', type=int, default='5', help='Number of rounds that are to be fought in the battle (points are split between all rounds). Default: 5')
        parser.add_option('--battle_type', dest='battle_type', choices=['iterated', 'averaged'], default='iterated', help='Type of battle wrapper to be used. Possible options: iterated, averaged. Default: iterated')
        parser.add_option('--points', dest='points', type=int, default='100', help='Number of points that are to be fought for. Default: 100')
        parser.add_option('--do_not_count_points', dest='do_not_count_points', action='store_true', help='If set, points are not calculated for the run.')
        parser.add_option('--silent', dest='silent', action='store_true', help='Disable forking the logging output to stderr.')
        parser.add_option('--ui', dest='display_ui', action='store_true', help='If set, the program sets the --silent option and displays a small ui on STDOUT that shows the progress of the battles.')

        (options, args) = parser.parse_args()

        display_ui = options.display_ui
        if display_ui:
            options.silent = True

        solvers = options.solvers.split(',')
        generators = options.generators.split(',')
        team_names = options.team_names.split(',')

        if len(solvers) != len(generators) or len(solvers) != len(team_names) or len(team_names) != len(generators):
            sys.exit('The number of provided generator paths ({}), solver paths ({}) and group numbers ({}) is not equal!'.format(len(generators), len(solvers), len(team_names)))

        problem_path = Path(problem_path)
        options.config = Path(options.config)
        solvers = [Path(s) for s in solvers]
        generators = [Path(g) for g in generators]
        _exit_if_path_nonexistent(problem_path)
        _exit_if_path_nonexistent(options.config)
        for solver_path in solvers:
            _exit_if_path_nonexistent(solver_path)
        for generator_path in generators:
            _exit_if_path_nonexistent(generator_path)

        logger = setup_logging(options.logging_path, options.verbose_logging, options.silent)

        problem = import_problem_from_path(problem_path)
        if not problem:
            sys.exit(1)

        logger.debug('Options for this run: {}'.format(options))
        logger.debug('Contents of sys.argv: {}'.format(sys.argv))
        logger.debug('Using additional configuration options from file "%s".', options.config)
        config = ConfigParser()
        config.read(options.config)

        teams: list[Team] = []
        for name, generator, solver in zip(team_names, generators, solvers):
            try:
                teams.append(Team(name, generator, solver, float(config["run_parameters"]["timeout_build"])))
            except (ValueError, DockerError):
                logger.warning(f"Building generators and solvers for team {name} failed, they will be excluded!")

        fight_handler = FightHandler(problem, config)
        battle_wrapper = initialize_wrapper(options.battle_type, config)
        match = Match(fight_handler, battle_wrapper, teams, rounds=options.battle_rounds)

        ui = None
        if display_ui:
            ui = Ui()
            match.attach(ui)

        results = match.run()

        if display_ui:
            match.detach(ui)
            ui.restore()

        logger.info('#' * 78)
        logger.info('\n{}'.format(match.format_match_data_as_utf8()))
        if not options.do_not_count_points:
            points = match.calculate_points(options.points)

            for team_name in match.teams:
                logger.info('Group {} gained {:.1f} points.'.format(str(team_name), points[str(team_name)]))
    except KeyboardInterrupt:
        try:
            logger.critical("Received keyboard interrupt, terminating execution.")  # type: ignore
        except NameError:
            raise SystemExit("Received keyboard interrupt, terminating execution.")

if __name__ == "__main__":
    main()