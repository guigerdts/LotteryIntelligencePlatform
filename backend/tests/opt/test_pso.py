"""Tests for opt/pso — Particle Swarm Optimization optimizer (OA-02)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.pso import PsoOptimizer
from backend.app.opt.search_space import SearchParam, SearchSpace


def _simple_objective(params: dict) -> Decimal:
    """Simple objective: maximize -(x - 0.5)^2."""
    x = params.get("x", 0.0)
    return Decimal(str(-((x - 0.5) ** 2)))


def test_pso_produces_result() -> None:
    """PSO returns an OptResult with best_params and best_fitness."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=10)
    optimizer = PsoOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert "x" in result.best_params
    assert isinstance(result.best_fitness, Decimal)
    assert result.n_evaluations > 0


def test_pso_convergence_history() -> None:
    """PSO produces convergence history with expected entries."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=10)
    optimizer = PsoOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert result.convergence.n_evaluations == 10


def test_pso_deterministic() -> None:
    """Same seed produces same result."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=10)
    optimizer = PsoOptimizer()
    r1 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    r2 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert r1.best_params == r2.best_params
    assert r1.best_fitness == r2.best_fitness


def test_pso_global_best_monotonic() -> None:
    """PSO global best fitness is monotonically non-decreasing."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=20)
    optimizer = PsoOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    fitnesses = [e.best_fitness for e in result.convergence.history]
    for i in range(1, len(fitnesses)):
        assert fitnesses[i] >= fitnesses[i - 1]
