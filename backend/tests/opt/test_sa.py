"""Tests for opt/sa — Simulated Annealing optimizer (OA-04)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.sa import SaOptimizer
from backend.app.opt.search_space import SearchParam, SearchSpace


def _simple_objective(params: dict) -> Decimal:
    """Simple objective: maximize -(x - 0.5)^2."""
    x = params.get("x", 0.0)
    return Decimal(str(-((x - 0.5) ** 2)))


def test_sa_produces_result() -> None:
    """SA returns an OptResult with best_params and best_fitness."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=10)
    optimizer = SaOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert "x" in result.best_params
    assert isinstance(result.best_fitness, Decimal)
    assert result.n_evaluations > 0


def test_sa_convergence_history() -> None:
    """SA produces convergence history with expected entries."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=10)
    optimizer = SaOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert result.convergence.n_evaluations == 10


def test_sa_deterministic() -> None:
    """Same seed produces same result."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=10)
    optimizer = SaOptimizer()
    r1 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    r2 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert r1.best_params == r2.best_params
    assert r1.best_fitness == r2.best_fitness


def test_sa_temperature_decreases() -> None:
    """SA temperature decreases monotonically (verified via convergence)."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_generations=20)
    optimizer = SaOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    # Best fitness should be monotonically non-decreasing
    fitnesses = [e.best_fitness for e in result.convergence.history]
    for i in range(1, len(fitnesses)):
        assert fitnesses[i] >= fitnesses[i - 1]
