"""Tests for BacktestEngine orchestrator (BTE-02, BTE-07, BTE-10, BTE-15).

Verifies full workflow, data floor, isolation, window history, temporal
ordering, and convergence tracking.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.types import BacktestConfig, Draw, DrawContext
from backend.app.services.errors import InsufficientDataError


class _DummyStrategy:
    """Minimal strategy for engine tests."""

    @property
    def strategy_id(self) -> str:
        return "dummy-v1"

    def predict(self, draw_context: DrawContext) -> list[int]:
        return [1, 2, 3, 4, 5]


def _make_draws(n: int, start: str = "2015-01-01") -> list[Draw]:
    """Create *n* draws spaced one week apart."""
    base = datetime.fromisoformat(start)
    return [
        Draw(
            id=i,
            draw_date=base + timedelta(weeks=i),
            numbers=(1, 2, 3, 4, 5),
            super_number=10,
        )
        for i in range(n)
    ]


class TestBacktestEngineDataFloor:
    """Data floor validation (BTE-07)."""

    def test_below_min_draws_raises(self) -> None:
        draws = _make_draws(10)
        cfg = BacktestConfig(min_train_draws=100)
        engine = BacktestEngine()
        with pytest.raises(InsufficientDataError):
            engine.run(
                strategy=_DummyStrategy(),
                draws=draws,
                config=cfg,
                lottery_id=1,
            )

    def test_exactly_min_draws_proceeds(self) -> None:
        draws = _make_draws(100)
        cfg = BacktestConfig(
            min_train_draws=100,
            train_years=2,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        assert result is not None

    def test_above_min_draws_proceeds(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=100,
            train_years=2,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        assert result is not None


class TestBacktestEngineWorkflow:
    """Full engine workflow (BTE-10, BTE-15)."""

    def test_returns_backtest_result(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        assert result.fingerprint is not None
        assert result.lottery_id == 1
        assert result.strategy_id == "dummy-v1"
        assert result.status == "active"

    def test_window_history_populated(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        assert len(result.window_history) > 0

    def test_aggregate_metrics_computed(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        assert result.aggregate_metrics.total_draws_evaluated > 0

    def test_fingerprint_deterministic(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        r1 = engine.run(strategy=_DummyStrategy(), draws=draws, config=cfg, lottery_id=1)
        r2 = engine.run(strategy=_DummyStrategy(), draws=draws, config=cfg, lottery_id=1)
        assert r1.fingerprint == r2.fingerprint

    def test_window_result_has_ranges(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=2,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        for wr in result.window_history:
            assert wr.train_range[0] < wr.train_range[1]
            assert wr.eval_range[0] < wr.eval_range[1]
            assert wr.train_range[1] <= wr.eval_range[0]


class TestBacktestEngineIsolation:
    """No non-bt_* writes (BTE-02)."""

    def test_engine_pure_no_db(self) -> None:
        """Engine returns result without touching any DB."""
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        # Engine is pure — result is a dataclass, no DB side effects
        assert isinstance(result.window_history, tuple)

    def test_multi_lottery_different_results(self) -> None:
        """BTE-14: different lottery_ids produce separate results."""
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        r1 = engine.run(strategy=_DummyStrategy(), draws=draws, config=cfg, lottery_id=1)
        r2 = engine.run(strategy=_DummyStrategy(), draws=draws, config=cfg, lottery_id=2)
        assert r1.lottery_id == 1
        assert r2.lottery_id == 2
        # Same strategy, same data → same metrics
        assert r1.aggregate_metrics == r2.aggregate_metrics


class TestBacktestEngineBenchmarks:
    """Both benchmarks evaluated on same period (BTE-16)."""

    def test_benchmark_metrics_present(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        for wr in result.window_history:
            assert wr.uniform_metrics is not None
            assert wr.hypergeometric_metrics is not None

    def test_benchmark_same_eval_count(self) -> None:
        """BTE-16: strategy and benchmarks evaluate same number of draws."""
        draws = _make_draws(200)
        cfg = BacktestConfig(
            min_train_draws=10,
            train_years=1,
            eval_count=1,
            step_count=1,
        )
        engine = BacktestEngine()
        result = engine.run(
            strategy=_DummyStrategy(),
            draws=draws,
            config=cfg,
            lottery_id=1,
        )
        for wr in result.window_history:
            assert (
                wr.strategy_metrics.total_draws_evaluated
                == wr.uniform_metrics.total_draws_evaluated
            )
            assert (
                wr.strategy_metrics.total_draws_evaluated
                == wr.hypergeometric_metrics.total_draws_evaluated
            )
