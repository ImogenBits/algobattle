"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from __future__ import annotations
from argparse import ArgumentParser
from contextlib import ExitStack
from functools import partial
import sys
import logging
import datetime as dt
from pathlib import Path
from typing import Any, ClassVar, Literal
import tomllib

from pydantic import BaseModel, Field

from algobattle.battle import Battle
from algobattle.docker_util import DockerConfig, RunParameters
from algobattle.match import MatchConfig, Match
from algobattle.problem import Problem
from algobattle.team import TeamHandler, TeamInfo
from algobattle.ui import Ui
from algobattle.util import check_path, getattr_set


def setup_logging(logging_path: Path, verbose_logging: bool, silent: bool):
    """Creates and returns a parent logger.

    Parameters
    ----------
    logging_path : Path
        Path to folder where the logfile should be stored at.
    verbose_logging : bool
        Flag indicating whether to include debug messages in the output
    silent : bool
        Flag indicating whether not to pipe the logging output to stderr.

    Returns
    -------
    logger : Logger
        The Logger object.
    """
    common_logging_level = logging.INFO

    if verbose_logging:
        common_logging_level = logging.DEBUG

    Path(logging_path).mkdir(exist_ok=True)

    t = dt.datetime.now()
    current_timestamp = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}"
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

    logger.info(f"You can find the log files for this run in {logging_path}")
    return logger


class Config(BaseModel):
    """Pydantic model to parse the config file."""

    problem: Path
    teams: list[TeamInfo] = []
    display: Literal["silent", "logs", "ui"] = "logs"
    logs: Path = Field(Path.home() / ".algobattle_logs", cli_alias="logging_path")
    match: MatchConfig
    docker: DockerConfig


def parse_cli_args(args: list[str]) -> tuple[ProgramConfig, DockerConfig, MatchConfig, Battle.Config]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument("problem", type=check_path, help="Path to a folder with the problem file.")
    parser.add_argument("--config", type=partial(check_path, type="file"), help="Path to a config file, defaults to '{problem} / config.toml'.")
    parser.add_argument("--logging_path", type=partial(check_path, type="dir"), help="Folder that logs are written into, defaults to '~/.algobattle_logs'.")
    parser.add_argument("--display", choices=["silent", "logs", "ui"], help="Choose output mode, silent disables all output, logs displays the battle logs on STDERR, ui displays a small GUI showing the progress of the battle. Default: logs.")

    parser.add_argument("--verbose", "-v", dest="verbose", action="store_const", const=True, help="More detailed log output.")
    parser.add_argument("--safe_build", action="store_const", const=True, help="Isolate docker image builds from each other. Significantly slows down battle setup but closes prevents images from interfering with each other.")

    parser.add_argument("--battle_type", choices=[name.lower() for name in Battle.all()], help="Type of battle to be used.")
    parser.add_argument("--rounds", type=int, help="Number of rounds that are to be fought in the battle (points are split between all rounds).")
    parser.add_argument("--points", type=int, help="number of points distributed between teams.")

    parser.add_argument("--timeout_build", type=float, help="Timeout for the build step of each docker image.")
    parser.add_argument("--timeout_generator", type=float, help="Time limit for the generator execution.")
    parser.add_argument("--timeout_solver", type=float, help="Time limit for the solver execution.")
    parser.add_argument("--space_generator", type=int, help="Memory limit for the generator execution, in MB.")
    parser.add_argument("--space_solver", type=int, help="Memory limit the solver execution, in MB.")
    parser.add_argument("--cpus_generator", type=int, help="Number of cpu cores used for generator container execution.")
    parser.add_argument("--cpus_solver", type=int, help="Number of cpu cores used for solver container execution.")

    # battle types have their configs automatically added to the CLI args
    for battle_name, battle in Battle.all().items():
        group = parser.add_argument_group(battle_name)
        for name, kwargs in battle.Config.as_argparse_args():
            group.add_argument(f"--{battle_name.lower()}_{name}", **kwargs)

    parsed = parser.parse_args(args)

    if parsed.battle_type is not None:
        parsed.battle_type = Battle.all()[parsed.battle_type]
    cfg_path = parsed.config if parsed.config is not None else parsed.problem / "config.toml"
    if cfg_path.is_file():
        with open(cfg_path, "rb") as file:
            try:
                config_dict = tomllib.load(file)
            except tomllib.TOMLDecodeError as e:
                raise ValueError(f"The config file at {cfg_path} is not a properly formatted TOML file!\n{e}")
    else:
        config_dict = {}

    config = Config.parse_obj(config_dict)
    config.problem = parsed.problem
    if not config.teams:
        config.teams.append(TeamInfo(
            name="team_0",
            generator=config.problem / "generator",
            solver=config.problem / "solver",
        ))

    program_config = ProgramConfig(teams=teams, **getattr_set(parsed, "problem", "display", "logs"))

    match_config = MatchConfig.from_dict(config_dict.get("match", {}))
    for name in vars(match_config):
        if getattr(parsed, name) is not None:
            setattr(match_config, name, getattr(parsed, name))

    docker_params = config_dict.get("docker", {})
    docker_config = DockerConfig(
        build_timeout=docker_params.get("build_timeout"),
        generator=RunParameters(**docker_params.get("generator", {})),
        solver=RunParameters(**docker_params.get("solver", {})),
    )
    if getattr(parsed, "timeout_build") is not None:
        object.__setattr__(docker_config, "build_timeout", parsed.timeout_build)
    for role in ("generator", "solver"):
        role_config = getattr(docker_config, role)
        for name in vars(role_config):
            cli_name = f"{name}_{role}"
            if getattr(parsed, cli_name) is not None:
                object.__setattr__(role_config, name, getattr(parsed, cli_name))

    battle_config = match_config.battle_type.Config(**config_dict.get(match_config.battle_type.name().lower(), {}))
    for name in vars(battle_config):
        cli_name = f"{match_config.battle_type.name().lower()}_{name}"
        if getattr(parsed, cli_name) is not None:
            setattr(battle_config, name, getattr(parsed, cli_name))

    return program_config, docker_config, match_config, battle_config


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        program_config, docker_config, match_config, battle_config = parse_cli_args(sys.argv[1:])
        logger = setup_logging(program_config.logs, match_config.verbose, program_config.display != "logs")

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = Problem.import_from_path(program_config.problem)
        with TeamHandler.build(program_config.teams, problem, docker_config) as teams, ExitStack() as stack:
            if program_config.display == "ui":
                ui = Ui()
                stack.enter_context(ui)
            else:
                ui = None

            result = Match.run(match_config, battle_config, problem, teams, ui)

            logger.info('#' * 78)
            logger.info(result.display())
            if match_config.points > 0:
                points = result.calculate_points(match_config.points)
                for team, pts in points.items():
                    logger.info(f"Group {team} gained {pts:.1f} points.")

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


if __name__ == "__main__":
    main()
