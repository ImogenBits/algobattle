"""Tests for all docker functions."""
from unittest import IsolatedAsyncioTestCase, main as run_tests
import random
from pathlib import Path

from algobattle.docker_util import (
    AdvancedBuildArgs,
    AdvancedRunArgs,
    ExecutionTimeout,
    BuildError,
    ExecutionError,
    Generator,
    Image,
    RunConfig,
    Solver,
)
from algobattle.util import Role
from . import testsproblem
from .testsproblem.problem import TestProblem, TestInstance, TestSolution


class ImageTests(IsolatedAsyncioTestCase):
    """Tests for the Image functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the path to the docker containers."""
        cls.problem_path = Path(testsproblem.__file__).parent
        cls.build_kwargs = AdvancedBuildArgs().kwargs
        cls.run_kwargs = AdvancedRunArgs().kwargs

    @classmethod
    def dockerfile(cls, name: str) -> Path:
        return cls.problem_path / name

    async def test_build_timeout(self):
        """Raises an error if building a container runs into a timeout."""
        with self.assertRaises(BuildError), await Image.build(
            self.problem_path / "build_timeout",
            role=Role.generator,
            timeout=0.5,
            advanced_args=self.build_kwargs,
            max_size=None,
        ):
            pass

    async def test_build_failed(self):
        """Raises an error if building a docker container fails for any reason other than a timeout."""
        with self.assertRaises(BuildError), await Image.build(
            self.problem_path / "build_error", role=Role.generator, advanced_args=self.build_kwargs, max_size=None
        ):
            pass

    async def test_build_successful(self):
        """Runs successfully if a docker container builds successfully."""
        with await Image.build(
            self.problem_path / "generator", role=Role.generator, advanced_args=self.build_kwargs, max_size=None
        ):
            pass

    async def test_build_nonexistant_path(self):
        """Raises an error if the path to the container does not exist in the file system."""
        with self.assertRaises(RuntimeError):
            nonexistent_file = None
            while nonexistent_file is None or nonexistent_file.exists():
                nonexistent_file = Path(str(random.randint(0, 2**80)))
            with await Image.build(
                nonexistent_file, role=Role.generator, advanced_args=self.build_kwargs, max_size=None
            ):
                pass

    async def test_run_timeout(self):
        """`Image.run()` raises an error when the container times out."""
        with await Image.build(
            self.problem_path / "generator_timeout", role=Role.generator, advanced_args=self.build_kwargs, max_size=None
        ) as image, self.assertRaises(ExecutionTimeout):
            await image.run(timeout=1.0, space=None, cpus=1, set_cpus=None, run_kwargs=self.run_kwargs)

    async def test_run_error(self):
        """Raises an error if the container doesn't run successfully."""
        with (
            self.assertRaises(ExecutionError),
            await Image.build(
                self.problem_path / "generator_execution_error",
                role=Role.generator,
                advanced_args=self.build_kwargs,
                max_size=None,
            ) as image,
        ):
            await image.run(timeout=10.0, space=None, cpus=1, set_cpus=None, run_kwargs=self.run_kwargs)


class ProgramTests(IsolatedAsyncioTestCase):
    """Tests for the Program functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the config and problem objects."""
        cls.problem_path = Path(testsproblem.__file__).parent
        cls.config = RunConfig()
        cls.config_short = RunConfig(timeout=2)
        cls.instance = TestInstance(semantics=True)

    async def test_gen_lax_timeout(self):
        """The generator times out but still outputs a valid instance."""
        with await Generator.build(
            image=self.problem_path / "generator_timeout", problem=TestProblem, config=self.config_short
        ) as gen:
            res = await gen.run(5)
            self.assertIsNone(res.info.error)

    async def test_gen_strict_timeout(self):
        """The generator times out."""
        with await Generator.build(
            image=self.problem_path / "generator_timeout",
            problem=TestProblem,
            config=self.config_short,
            strict_timeouts=True,
        ) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionTimeout")

    async def test_gen_exec_err(self):
        """The generator doesn't execute properly."""
        with await Generator.build(
            image=self.problem_path / "generator_execution_error", problem=TestProblem, config=self.config
        ) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionError")

    async def test_gen_syn_err(self):
        """The generator outputs a syntactically incorrect solution."""
        with await Generator.build(
            image=self.problem_path / "generator_syntax_error", problem=TestProblem, config=self.config
        ) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "EncodingError")

    async def test_gen_sem_err(self):
        """The generator outputs a semantically incorrect solution."""
        with await Generator.build(
            image=self.problem_path / "generator_semantics_error", problem=TestProblem, config=self.config
        ) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ValidationError")

    async def test_gen_succ(self):
        """The generator returns the fixed instance."""
        with await Generator.build(
            image=self.problem_path / "generator", problem=TestProblem, config=self.config
        ) as gen:
            res = await gen.run(5)
            correct = TestInstance(semantics=True)
            self.assertEqual(res.instance, correct)

    async def test_sol_strict_timeout(self):
        """The solver times out."""
        with await Solver.build(
            image=self.problem_path / "solver_timeout",
            problem=TestProblem,
            config=self.config_short,
            strict_timeouts=True,
        ) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionTimeout")

    async def test_sol_lax_timeout(self):
        """The solver times out but still outputs a correct solution."""
        with await Solver.build(
            image=self.problem_path / "solver_timeout", problem=TestProblem, config=self.config_short
        ) as sol:
            res = await sol.run(self.instance, 5)
            self.assertIsNone(res.info.error)

    async def test_sol_exec_err(self):
        """The solver doesn't execute properly."""
        with await Solver.build(
            image=self.problem_path / "solver_execution_error", problem=TestProblem, config=self.config
        ) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionError")

    async def test_sol_syn_err(self):
        """The solver outputs a syntactically incorrect solution."""
        with await Solver.build(
            image=self.problem_path / "solver_syntax_error", problem=TestProblem, config=self.config
        ) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "EncodingError")

    async def test_sol_sem_err(self):
        """The solver outputs a semantically incorrect solution."""
        with await Solver.build(
            image=self.problem_path / "solver_semantics_error", problem=TestProblem, config=self.config
        ) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ValidationError")

    async def test_sol_succ(self):
        """The solver outputs a solution with a low quality."""
        with await Solver.build(image=self.problem_path / "solver", problem=TestProblem, config=self.config) as sol:
            res = await sol.run(self.instance, 5)
            correct = TestSolution(semantics=True, quality=True)
            self.assertEqual(res.solution, correct)


if __name__ == "__main__":
    run_tests()
