"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Literal, Protocol, TypeVar, get_type_hints
from pydantic import BaseModel

from algobattle.util import inherit_docs

logger = logging.getLogger("algobattle.problem")


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


class Hidden:
    """Marker class indicating that a field will not be parsed into the solver input."""
    pass


_Self = TypeVar("_Self", bound="ProblemData")


class ProblemData(Protocol):
    """Represents problem data that docker containers can interact with."""

    @abstractmethod
    @classmethod
    def decode(cls: type[_Self], source_dir: Path, size: int) -> _Self:
        """Parses the container output into problem data."""
        ...

    @abstractmethod
    def encode(self, target_dir: Path, size: int, team: Literal["generator", "solver"]) -> None:
        """Encodes the problem data into files that can be passed to docker containers."""
        ...


class Instance(ProblemData, Protocol):
    """A specific instance of a problem."""

    def check_semantics(self, size: int) -> bool:
        """Validates that the parsed data is semantically correct."""
        ...


_Instance = TypeVar("_Instance", bound=Instance, contravariant=True)


class Solution(Generic[_Instance], ProblemData, Protocol):
    """A solution of a problem instance."""

    def check_semantics(self, size: int, instance: _Instance) -> bool:
        """Validates that the parsed data is semantically correct."""
        ...


_Self = TypeVar("_Self", bound="_JsonEncodable")


class _JsonEncodable(BaseModel, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    filename: ClassVar[str]

    @inherit_docs
    @classmethod
    def decode(cls: type[_Self], source_dir: Path, size: int) -> _Self:
        try:
            return cls.parse_file(source_dir / cls.filename)
        except Exception as e:
            raise ContainerError from e

    @inherit_docs
    def encode(self, target_dir: Path, size: int, team: Literal["generator", "solver"]) -> None:
        try:
            with open(target_dir / self.filename, "w") as f:
                f.write(self.json(exclude=self._excludes()))
        except Exception as e:
            raise ContainerError from e

    @classmethod
    def _excludes(cls) -> dict[str | int, Any]:
        excludes = {}
        for name, annotation in get_type_hints(cls, include_extras=True).items():
            if hasattr(annotation, "__metadata__") and Hidden in annotation.__metadata__:
                excludes[name] = True
            elif issubclass(annotation, _JsonEncodable):
                excludes[name] = annotation._excludes()
        return excludes


class JsonInstance(_JsonEncodable, Instance, ABC):
    """Represents a specific instance of a problem."""

    filename = "instance.json"

    def check_semantics(self, size: int) -> bool:
        return True


class JsonSolution(_JsonEncodable, Solution[_Instance], ABC):
    """Represents a potential solution to an instance of a problem."""

    filename = "solution.json"

    def check_semantics(self, size: int, instance: _Instance) -> bool:
        return True


_Solution = TypeVar("_Solution", bound=Solution[Instance])
_Self = TypeVar("_Self", bound="Problem[Any, Any]")


@dataclass(kw_only=True, frozen=True)
class Problem(Generic[_Instance, _Solution]):
    """Dataclass specifying what a problem's instances and solutions look like."""

    name: str
    """Name of the problem."""
    start_size: int = 1
    """Smallest valid size for this problem"""
    instance_type: type[_Instance]
    """Type of the instances of this problem."""
    solution_type: type[_Solution]
    """Type of the solutions of this problem."""
    calculate_score: Callable[[_Instance, _Solution], float]
    """Scores a proposed solution for an instance.
    
    Return values are clamped to fall inside [0, 1].
    A value of 0 indicating that the solver failed completely
    and 1 that it solved the instance perfectly.
    """

    @classmethod
    def import_from_path(cls: type[_Self], path: Path) -> _Self:
        """Try to import and initialize a Problem object from a given path.

        Parameters
        ----------
        path : Path
            Path in the file system to a problem folder.

        Returns
        -------
        Problem
            Returns an object of the problem.

        Raises
        ------
        ValueError
            If the path doesn't point to a file containing a valid problem.
        """
        if not (path / "__init__.py").is_file():
            raise ValueError

        try:
            spec = importlib.util.spec_from_file_location("problem", path / "__init__.py")
            assert spec is not None
            assert spec.loader is not None
            Problem = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = Problem
            spec.loader.exec_module(Problem)
            return Problem.problem
        except ImportError as e:
            logger.critical(f"Importing the given problem failed with the following exception: {e}")
            raise ValueError from e


@dataclass(kw_only=True, frozen=True)
class DecisionProblem(Problem[_Instance, _Solution]):
    """A :cls:`Problem` where all valid solutions are equally good."""

    calculate_score: Callable[[_Instance, _Solution], float] = field(init=False, default=lambda i, s: 1)


class OptimizationSolution(Solution[_Instance], Protocol):
    """A solution for an optimization problem."""

    @abstractmethod
    def valuate(self) -> float:
        """Evaluates this solution."""
        raise NotImplementedError


class OptimizationInstance(Instance, Protocol):
    """An instance that contains an optimal solution against which other solutions are checked."""

    solution: OptimizationSolution["OptimizationInstance"]


_OptiInst, _OptiSol = TypeVar("_OptiInst", bound=OptimizationInstance), TypeVar("_OptiSol", bound=OptimizationSolution[OptimizationInstance])


def approximation_ratio(direction: Literal["minimize", "maximize"]) -> Callable[[_OptiInst, OptimizationSolution[_OptiInst]], float]:
    def score(instance: _OptiInst, solution: OptimizationSolution[_OptiInst]) -> float:
        gen = instance.solution.valuate()
        sol = solution.valuate()
        if gen == 0:
            return 1
        if sol == 0:
            return 0
        match direction:
            case "minimize":
                score = gen / sol
            case "maximize":
                score = sol / gen
        return max(0, min(1, score))
    return score
