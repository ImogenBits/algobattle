"""Module containing helper classes related to teams."""
from abc import abstractmethod
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Iterator, Protocol, Self

from algobattle.docker_util import DockerConfig, Generator, Solver
from algobattle.problem import Problem
from algobattle.util import ExceptionInfo, Role


_team_names: set[str] = set()


class BuildUiProxy(Protocol):
    """Provides and interface for the build process to update the ui."""

    @abstractmethod
    def start_build(self, team: str, role: Role, timeout: float | None) -> None:
        """Informs the ui that a new program is being built."""

    @abstractmethod
    def finish_build(self) -> None:
        """Informs the ui that the current build has been finished."""

    @abstractmethod
    def initialize_programs(self) -> None:
        """Informs the ui that the programs are being initialized."""

    @abstractmethod
    def finish_init_programs(self) -> None:
        """Informs the ui that all programs have been initialized."""


@dataclass
class TeamInfo:
    """The config parameters defining a team."""

    name: str
    generator: Path
    solver: Path

    async def build(self, problem: type[Problem], config: DockerConfig, ui: BuildUiProxy) -> "Team":
        """Builds the specified docker files into images and return the corresponding team.

        Raises:
            ValueError: If the team name is already in use.
            DockerError: If the docker build fails for some reason
        """
        name = self.name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if name in _team_names:
            raise ValueError
        ui.start_build(name, "generator", config.build_timeout)
        generator = await Generator.build(self.generator, problem, config.generator, config.build_timeout)
        ui.finish_build()
        try:
            ui.start_build(name, "solver", config.build_timeout)
            solver = await Solver.build(self.solver, problem, config.solver, config.build_timeout)
            ui.finish_build()
        except Exception:
            generator.remove()
            raise
        return Team(name, generator, solver)


@dataclass
class Team:
    """Team class responsible for holding basic information of a specific team."""

    name: str
    generator: Generator
    solver: Solver

    def __post_init__(self) -> None:
        """Creates a team object.

        Raises:
            ValueError: If the team name is already in use.
        """
        super().__init__()
        self.name = self.name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if self.name in _team_names:
            raise ValueError
        _team_names.add(self.name)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Team):
            return self.name == o.name
        else:
            return False

    def __hash__(self) -> int:
        return hash(self.name)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.cleanup()

    def cleanup(self) -> None:
        """Removes the built docker images."""
        self.generator.remove()
        self.solver.remove()
        _team_names.remove(self.name)


@dataclass(frozen=True)
class Matchup:
    """Represents an individual matchup of teams."""

    generator: Team
    solver: Team

    def __iter__(self) -> Iterator[Team]:
        yield self.generator
        yield self.solver

    def __repr__(self) -> str:
        return f"Matchup({self.generator.name}, {self.solver.name})"


@dataclass
class TeamHandler:
    """Handles building teams and cleaning them up."""

    active: list[Team] = field(default_factory=list)
    excluded: dict[str, ExceptionInfo] = field(default_factory=dict)

    @classmethod
    async def build(
        cls, infos: list[TeamInfo], problem: type[Problem], config: DockerConfig, ui: BuildUiProxy,
    ) -> Self:
        """Builds the programs of every team.

        Attempts to build the programs of every team. If any build fails, that team will be excluded and all its
        programs cleaned up.
        If `config.safe_build` is set, then each team's images will be archived before the other team's images are
        built. This prevents teams to be able to see already built images during their build process and thus see data
        they are not entitled to.

        Args:
            infos: Teams that participate in the match.
            problem: Problem class that the match will be fought with.
            config: Config options.

        Returns:
            :cls:`TeamHandler` containing the info about the participating teams.
        """
        handler = cls()
        for info in infos:
            try:
                team = await info.build(problem, config, ui)
                handler.active.append(team)
            except Exception as e:
                handler.excluded[info.name] = ExceptionInfo.from_exception(e)
        return handler

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type, _value_, _traceback):
        for team in self.active:
            team.cleanup()

    @property
    def grouped_matchups(self) -> list[tuple[Matchup, Matchup]]:
        """All matchups, grouped by the involved teams.

        Each tuple's first matchup has the first team in the group generating, the second has it solving.
        """
        return [(Matchup(*g), Matchup(*g[::-1])) for g in combinations(self.active, 2)]

    @property
    def matchups(self) -> list[Matchup]:
        """All matchups that will be fought."""
        if len(self.active) == 1:
            return [Matchup(self.active[0], self.active[0])]
        else:
            return [m for pair in self.grouped_matchups for m in pair]
