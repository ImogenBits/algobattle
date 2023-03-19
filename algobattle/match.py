"""Central managing module for an algorithmic battle."""
from __future__ import annotations
import logging
from typing import Self

from pydantic import BaseModel, validator
from anyio import run, create_task_group, CapacityLimiter, TASK_STATUS_IGNORED
from anyio.to_thread import current_default_thread_limiter
from anyio.abc import TaskStatus

from algobattle.battle import Battle, Iterated
from algobattle.team import Matchup, TeamHandler, Team
from algobattle.problem import Problem

logger = logging.getLogger("algobattle.match")


class MatchConfig(BaseModel):
    """Parameters determining the match execution."""

    battle_type: type[Battle] = Iterated
    points: int = 100
    parallel_battles: int = 1

    @validator("battle_type", pre=True)
    def parse_battle_type(cls, value):
        """Parses the battle type class object from its name."""
        if isinstance(value, str):
            all = Battle.all()
            if value in all:
                return all[value]
            else:
                raise ValueError
        elif issubclass(value, Battle):
            return value
        else:
            raise TypeError


class Match:
    """The Result of a whole Match."""

    def __init__(
        self,
        config: MatchConfig,
        battle_config: Battle.Config,
        problem: type[Problem],
        teams: TeamHandler,
    ) -> None:
        self.results: dict[Matchup, Battle] = {}
        self.config = config
        self.battle_config = battle_config
        self.problem = problem
        self.teams = teams
        super().__init__()

    @classmethod
    async def _run_battle(
        cls,
        battle: Battle,
        matchup: Matchup,
        config: Battle.Config,
        min_size: int,
        limiter: CapacityLimiter,
        *,
        task_status: TaskStatus = TASK_STATUS_IGNORED,
    ) -> None:
        async with limiter:
            task_status.started()
            try:
                await battle.run_battle(matchup.generator.generator, matchup.solver.solver, config, min_size)
            except Exception as e:
                logger.critical(f"Unhandeled error during execution of battle!\n{e}")

    @classmethod
    async def run(
        cls,
        config: MatchConfig,
        battle_config: Battle.Config,
        problem: type[Problem],
        teams: TeamHandler,
    ) -> Self:
        """Executes a match with the specified parameters."""
        result = cls(config, battle_config, problem, teams)
        limiter = CapacityLimiter(config.parallel_battles)
        current_default_thread_limiter().total_tokens = config.parallel_battles
        async with create_task_group() as tg:
            for matchup in teams.matchups:
                battle = config.battle_type()
                result.results[matchup] = battle
                await tg.start(cls._run_battle, battle, matchup, battle_config, problem.min_size, limiter)
            return result

    @classmethod
    def run_sync(
        cls,
        config: MatchConfig,
        battle_config: Battle.Config,
        problem: type[Problem],
        teams: TeamHandler,
    ) -> Self:
        """Executes the match with the specified parameters in a new event loop."""
        return run(cls.run, config, battle_config, problem, teams)

    def calculate_points(self) -> dict[str, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        achievable_points = self.config.points
        if len(self.teams.active) == 0:
            return {}
        if len(self.teams.active) == 1:
            return {self.teams.active[0].name: achievable_points}

        points = {team.name: 0.0 for team in self.teams.active + self.teams.excluded}
        points_per_battle = round(achievable_points / (len(self.teams.active) - 1), 1)

        for home_matchup, away_matchup in self.teams.grouped_matchups:
            home_team: Team = getattr(home_matchup, self.config.battle_type.scoring_team)
            away_team: Team = getattr(away_matchup, self.config.battle_type.scoring_team)
            home_res = self.results[home_matchup]
            away_res = self.results[away_matchup]
            total_score = home_res.score() + away_res.score()
            if total_score == 0:
                # Default values for proportions, assuming no team manages to solve anything
                home_ratio = 0.5
                away_ratio = 0.5
            else:
                home_ratio = home_res.score() / total_score
                away_ratio = away_res.score() / total_score

            points[home_team.name] += round(points_per_battle * home_ratio, 1)
            points[away_team.name] += round(points_per_battle * away_ratio, 1)

        # we need to also add the points each team would have gotten fighting the excluded teams
        # each active team would have had one set of battles against each excluded team
        for team in self.teams.active:
            points[team.name] += points_per_battle * len(self.teams.excluded)

        return points
