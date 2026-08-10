"""Tests for opt/ga — Genetic Algorithm optimizer (OA-01)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.opt.ga import GaOptimizer
from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.search_space import SearchParam, SearchSpace


def _simple_objective(params: dict) -> Decimal:
    """Simple objective: maximize -(x - 0.5)^2."""
    x = params.get("x", 0.0)
    return Decimal(str(-((x - 0.5) ** 2)))


def test_ga_produces_result() -> None:
    """GA returns an OptResult with best_params and best_fitness."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=5)
    optimizer = GaOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert "x" in result.best_params
    assert isinstance(result.best_fitness, Decimal)
    assert result.n_evaluations > 0


def test_ga_convergence_history() -> None:
    """GA produces convergence history with expected entries."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=10)
    optimizer = GaOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert result.convergence.n_evaluations == 10
    eval_nums = [e.eval_num for e in result.convergence.history]
    assert eval_nums == list(range(1, 11))


def test_ga_deterministic() -> None:
    """Same seed produces same result."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=5)
    optimizer = GaOptimizer()
    r1 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    r2 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert r1.best_params == r2.best_params
    assert r1.best_fitness == r2.best_fitness


def test_ga_elitism() -> None:
    """GA preserves best individual across generations."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=20)
    optimizer = GaOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    # Best fitness should be monotonically non-decreasing
    fitnesses = [e.best_fitness for e in result.convergence.history]
    for i in range(1, len(fitnesses)):
        assert fitnesses[i] >= fitnesses[i - 1]
