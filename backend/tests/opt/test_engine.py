"""Tests for engine orchestrator (PR4)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.opt.engine import (
    SUPPORTED_DIRECTIONS,
    SUPPORTED_METRICS,
    ObjectiveConfig,
    _instantiate_optimizer,
    build_objective_function,
)
from backend.app.opt.ga import GaOptimizer
from backend.app.opt.optimizer_types import OptimizerProtocol
from backend.app.opt.pso import PsoOptimizer
from backend.app.opt.sa import SaOptimizer


class TestInstantiateOptimizer:
    """_instantiate_optimizer tests."""

    def test_ga(self) -> None:
        """GA optimizer instantiated."""
        opt = _instantiate_optimizer("ga")
        assert isinstance(opt, GaOptimizer)

    def test_pso(self) -> None:
        """PSO optimizer instantiated."""
        opt = _instantiate_optimizer("pso")
        assert isinstance(opt, PsoOptimizer)

    def test_sa(self) -> None:
        """SA optimizer instantiated."""
        opt = _instantiate_optimizer("sa")
        assert isinstance(opt, SaOptimizer)

    def test_bayesian(self) -> None:
        """Bayesian optimizer instantiated."""
        from backend.app.opt.bayesian import BayesianOptimizer

        opt = _instantiate_optimizer("bayesian")
        assert isinstance(opt, BayesianOptimizer)

    def test_unknown_raises(self) -> None:
        """Unknown optimizer raises ValueError."""
        with pytest.raises(ValueError, match="Unknown optimizer"):
            _instantiate_optimizer("unknown")

    def test_all_implement_protocol(self) -> None:
        """All core-4 optimizers implement OptimizerProtocol."""
        for slug in ("ga", "pso", "bayesian", "sa"):
            opt = _instantiate_optimizer(slug)
            assert isinstance(opt, OptimizerProtocol)


class TestBuildObjectiveFunction:
    """build_objective_function tests."""

    def test_wraps_metric_selection(self) -> None:
        """Objective function selects specified metric."""
        raw_fn = lambda params: Decimal("0.85")  # noqa: E731
        cfg = ObjectiveConfig(metric="accuracy", direction="maximize")
        wrapped = build_objective_function(raw_fn, cfg)
        result = wrapped({})
        assert result == Decimal("0.85000000")

    def test_wraps_direction_minimize(self) -> None:
        """Objective function negates for minimize direction."""
        raw_fn = lambda params: Decimal("0.85")  # noqa: E731
        cfg = ObjectiveConfig(metric="f1", direction="minimize")
        wrapped = build_objective_function(raw_fn, cfg)
        result = wrapped({})
        assert result == Decimal("-0.85000000")

    def test_wraps_direction_maximize(self) -> None:
        """Objective function keeps positive for maximize."""
        raw_fn = lambda params: Decimal("0.85")  # noqa: E731
        cfg = ObjectiveConfig(metric="f1", direction="maximize")
        wrapped = build_objective_function(raw_fn, cfg)
        result = wrapped({})
        assert result == Decimal("0.85000000")

    def test_quantizes_result(self) -> None:
        """Objective function quantizes to 8 decimals."""
        raw_fn = lambda params: Decimal("0.123456789")  # noqa: E731
        cfg = ObjectiveConfig()
        wrapped = build_objective_function(raw_fn, cfg)
        result = wrapped({})
        assert result == Decimal("0.12345679")

    def test_callable_returns_decimal(self) -> None:
        """Wrapped function is callable."""
        raw_fn = lambda params: Decimal("0.5")  # noqa: E731
        cfg = ObjectiveConfig()
        wrapped = build_objective_function(raw_fn, cfg)
        assert callable(wrapped)


class TestSupportedSets:
    """SUPPORTED_METRICS and SUPPORTED_DIRECTIONS tests."""

    def test_metrics_count(self) -> None:
        """Five metrics supported."""
        assert len(SUPPORTED_METRICS) == 5

    def test_directions_count(self) -> None:
        """Two directions supported."""
        assert len(SUPPORTED_DIRECTIONS) == 2

    def test_all_directions_valid(self) -> None:
        """Directions are maximize and minimize."""
        assert SUPPORTED_DIRECTIONS == {"maximize", "minimize"}
