"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC, abstractmethod
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Literal, Protocol, TypeVar, get_type_hints
from pydantic import BaseModel

from algobattle.util import FileArchive


_Self = TypeVar("_Self", bound="Instance")


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


class Hidden:
    """Marker class indicating that a field will not be parsed into the solver input."""
    pass


class Instance(Protocol):
    """Represents a specific instance of a problem."""

    @abstractmethod
    @classmethod
    def parse(cls: type[_Self], source: FileArchive) -> _Self:
        """Parses the generator output into a problem instance."""
        raise NotImplementedError

    def check_semantics(self) -> bool:
        """Validates that the instance is semantically correct."""
        return True

    @abstractmethod
    def encode(self, **kwargs: dict[str, Any]) -> FileArchive:
        """Encodes the instance into files so it can be passed to docker containers."""
        raise NotImplementedError


_Self = TypeVar("_Self", bound="InstanceModel")


class InstanceModel(Instance, BaseModel):
    """Represents a specific instance of a problem.
    
    Populated with default implementations to make creating custom problems easier.
    """

    @classmethod
    def parse(cls: type[_Self], source: FileArchive) -> _Self:
        """Parses the generator output into a problem instance.
        
        The default implementation expects the object to be json encoded at a file 'instance.json'.
        """
        try:
            return cls.parse_raw(source[Path("instance.json")])
        except KeyError:
            raise ContainerError

    def encode(self, **kwargs: dict[str, Any]) -> FileArchive:
        """Encodes the instance into files so it can be passed to docker containers.
        
        By default a single file `instance.json` is generated and attributes annotated with :cls:`Hidden` are ignored.
        Battle wrappers may specify additional arguments via `kwargs` to fine tune the info passed to containers.
        """
        return FileArchive({Path("instance.json"): self.json(exclude=self._excludes()).encode()})

    @classmethod
    def _excludes(cls) -> dict[str | int, Any]:
        excludes = {}
        for name, annotation in get_type_hints(cls, include_extras=True).items():
            if hasattr(annotation, "__metadata__") and Hidden in annotation.__metadata__:
                excludes[name] = True
            elif issubclass(annotation, InstanceModel):
                excludes[name] = annotation._excludes()
        return excludes


_Self = TypeVar("_Self", bound="Solution")


class Solution(Protocol):
    """Represents a potential solution to an instance of a problem."""

    @abstractmethod
    @classmethod
    def parse(cls: type[_Self], source: FileArchive) -> _Self:
        """Parses the generator output into a problem instance."""
        raise NotImplementedError


_Self = TypeVar("_Self", bound="SolutionModel")


class SolutionModel(Solution, BaseModel):
    """Represents a potential solution to an instance of a problem.
    
    Populated with default implementations to make creating custom problems easier.
    """

    @classmethod
    def parse(cls: type[_Self], source: FileArchive) -> _Self:
        """Parses the generator output into a problem instance.
        
        The default implementation expects the object to be json encoded at a file 'solution.json'.
        """
        try:
            return cls.parse_raw(source[Path("solution.json")])
        except KeyError:
            raise ContainerError


_InstanceT, _SolutionT = TypeVar("_InstanceT", bound=Instance), TypeVar("_SolutionT", bound=Solution)


@dataclass(kw_only=True, frozen=True)
class Problem(Generic[_InstanceT, _SolutionT]):
    """Dataclass specifying what a problem's instances and solutions look like."""

    name: str
    """Name of the problem."""
    start_size: int = 1
    """Smallest valid size for this problem"""
    instance_type: type[_InstanceT]
    """Type of the instances of this problem."""
    solution_type: type[_SolutionT]
    """Type of the solutions of this problem."""
    calculate_score: Callable[[_InstanceT, _SolutionT], float]
    """Scores a proposed solution for an instance.
    
    Return values are clamped to fall inside [0, 1].
    A value of 0 indicating that the solver failed completely
    and 1 that it solved the instance perfectly.
    """


@dataclass(kw_only=True, frozen=True)
class DecisionProblem(Problem[_InstanceT, _SolutionT]):
    """A :cls:`Problem` where all valid solutions are equally good."""

    calculate_score: Callable[[_InstanceT, _SolutionT], float] = field(init=False, default=lambda i, s: 1)


class OptimizationInstance(Instance, Protocol):
    """An instance that contains an optimal solution against which other solutions are checked."""

    solution: "OptimizationSolution"


class OptimizationSolution(Solution, Protocol):
    """A solution for an optimization problem."""

    @abstractmethod
    def valuate(self) -> float:
        """Evaluates this solution."""
        raise NotImplementedError


_OptiInstT, _OptiSolT = TypeVar("_OptiInstT", bound=OptimizationInstance), TypeVar("_OptiSolT", bound=OptimizationSolution)


@dataclass(kw_only=True, frozen=True)
class OptimizationProblem(Problem[_OptiInstT, _OptiSolT]):
    """A :cls:`Problem` that compares solver solutions to an optimal solution provided by the generator."""

    direction: InitVar[Literal["minimize", "maximize"]]
    calculate_score: Callable[[_OptiInstT, _OptiSolT], float] = field(init=False)

    def __post_init__(self, direction: Literal["minimize", "maximize"]):
        def score(instance: _OptiInstT, solution: _OptiSolT) -> float:
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
        object.__setattr__(self, "calculate_score", score)
