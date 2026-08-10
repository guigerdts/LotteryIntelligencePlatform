"""Tests for opt/bayesian — Bayesian Optimization optimizer (OA-03)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.opt.bayesian import BayesianOptimizer
from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.search_space import SearchParam, SearchSpace


def _simple_objective(params: dict) -> Decimal:
    """Simple objective: maximize -(x - 0.5)^2."""
    x = params.get("x", 0.0)
    return Decimal(str(-((x - 0.5) ** 2)))


def test_bayesian_produces_result() -> None:
    """Bayesian returns an OptResult with best_params and best_fitness."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=10)
    optimizer = BayesianOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert "x" in result.best_params
    assert isinstance(result.best_fitness, Decimal)
    assert result.n_evaluations > 0


def test_bayesian_convergence_history() -> None:
    """Bayesian produces convergence history with expected entries."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=10)
    optimizer = BayesianOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert result.convergence.n_evaluations == 10


def test_bayesian_deterministic() -> None:
    """Same seed produces same result."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=10)
    optimizer = BayesianOptimizer()
    r1 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    r2 = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    assert r1.best_params == r2.best_params
    assert r1.best_fitness == r2.best_fitness


def test_bayesian_suggests_improving() -> None:
    """Bayesian optimization suggests params that improve over trials."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),))
    termination = TerminationConfig(max_evaluations=20)
    optimizer = BayesianOptimizer()
    result = optimizer.optimize(_simple_objective, space, seed=42, termination=termination)
    # Best fitness should be monotonically non-decreasing
    fitnesses = [e.best_fitness for e in result.convergence.history]
    for i in range(1, len(fitnesses)):
        assert fitnesses[i] >= fitnesses[i - 1]
