"""PR1 tests for Fase 10 BT: domain types and version constant.

These tests verify BTE-01, BTE-08, BTE-15:
- DrawContext, BacktestConfig, MetricSet, WindowResult, BacktestResult creation
- Immutable dataclasses (frozen=True)
- Decimal(20,8) quantization in MetricSet
- Version constant exists and is importable
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from backend.app.backtesting.types import (
    BacktestConfig,
    BacktestResult,
    Draw,
    DrawContext,
    MetricSet,
    WindowResult,
)
from backend.app.backtesting.version import BACKTEST_GENERATOR_VERSION


class TestDrawContext:
    """DrawContext creation and immutability (BTE-03)."""

    def test_create_draw_context(self) -> None:
        """Positive: DrawContext created with required fields."""
        draw = Draw(
            id=1,
            draw_date=datetime(2024, 1, 1),
            numbers=(1, 2, 3, 4, 5),
            super_number=10,
        )
        ctx = DrawContext(
            lottery_id=1,
            draw_date=datetime(2024, 6, 1),
            historical_draws=(draw,),
        )
        assert ctx.lottery_id == 1
        assert len(ctx.historical_draws) == 1

    def test_draw_context_is_frozen(self) -> None:
        """BTE-01: DrawContext is immutable."""
        draw = Draw(
            id=1,
            draw_date=datetime(2024, 1, 1),
            numbers=(1, 2, 3, 4, 5),
        )
        ctx = DrawContext(
            lottery_id=1,
            draw_date=datetime(2024, 6, 1),
            historical_draws=(draw,),
        )
        import pytest

        with pytest.raises(AttributeError):
            ctx.lottery_id = 2  # type: ignore[misc]

    def test_draw_context_with_feature_set(self) -> None:
        """DrawContext with optional feature_set."""
        draw = Draw(
            id=1,
            draw_date=datetime(2024, 1, 1),
            numbers=(1, 2, 3, 4, 5),
        )
        ctx = DrawContext(
            lottery_id=1,
            draw_date=datetime(2024, 6, 1),
            historical_draws=(draw,),
            feature_set={"features": [0.1, 0.2, 0.3]},
        )
        assert ctx.feature_set is not None


class TestBacktestConfig:
    """BacktestConfig creation and defaults (BTE-04, BTE-18)."""

    def test_default_config(self) -> None:
        """Positive: default config values."""
        cfg = BacktestConfig()
        assert cfg.train_years == 5
        assert cfg.eval_count == 1
        assert cfg.step_count == 1
        assert cfg.min_train_draws == 100
        assert cfg.seed == 42
        assert cfg.benchmark_type == "both"

    def test_custom_config(self) -> None:
        """Positive: custom config values."""
        cfg = BacktestConfig(
            train_years=3,
            eval_count=2,
            step_count=2,
            min_train_draws=50,
            seed=123,
            benchmark_type="uniform",
        )
        assert cfg.train_years == 3
        assert cfg.eval_count == 2
        assert cfg.benchmark_type == "uniform"

    def test_config_is_frozen(self) -> None:
        """BTE-04: BacktestConfig is immutable."""
        cfg = BacktestConfig()
        import pytest

        with pytest.raises(AttributeError):
            cfg.train_years = 10  # type: ignore[misc]


class TestMetricSet:
    """MetricSet creation and Decimal quantization (BTE-08)."""

    def test_create_metric_set(self) -> None:
        """Positive: MetricSet created with Decimal values."""
        ms = MetricSet(
            hit_rate=Decimal("0.75000000"),
            match_distribution={0: 5, 1: 3, 2: 2},
            average_matches=Decimal("1.20000000"),
            consistency_score=Decimal("0.80000000"),
            total_draws_evaluated=10,
        )
        assert ms.hit_rate == Decimal("0.75000000")
        assert ms.total_draws_evaluated == 10

    def test_metric_set_is_frozen(self) -> None:
        """BTE-08: MetricSet is immutable."""
        ms = MetricSet(
            hit_rate=Decimal("0.75000000"),
            match_distribution={},
            average_matches=Decimal("1.20000000"),
            consistency_score=Decimal("0.80000000"),
            total_draws_evaluated=10,
        )
        import pytest

        with pytest.raises(AttributeError):
            ms.hit_rate = Decimal("0.9")  # type: ignore[misc]

    def test_decimal_precision(self) -> None:
        """BTE-08: MetricSet values are Decimal(20,8)."""
        ms = MetricSet(
            hit_rate=Decimal("0.12345678"),
            match_distribution={},
            average_matches=Decimal("0.00000001"),
            consistency_score=Decimal("99999999.99999999"),
            total_draws_evaluated=1,
        )
        assert str(ms.hit_rate) == "0.12345678"
        assert str(ms.consistency_score) == "99999999.99999999"


class TestWindowResult:
    """WindowResult creation (BTE-15)."""

    def test_create_window_result(self) -> None:
        """Positive: WindowResult created with ranges and metrics."""
        ms = MetricSet(
            hit_rate=Decimal("0.50000000"),
            match_distribution={0: 1, 1: 1},
            average_matches=Decimal("0.50000000"),
            consistency_score=Decimal("0.50000000"),
            total_draws_evaluated=2,
        )
        wr = WindowResult(
            window_index=0,
            train_range=(0, 100),
            eval_range=(100, 101),
            strategy_metrics=ms,
            uniform_metrics=ms,
            hypergeometric_metrics=ms,
        )
        assert wr.window_index == 0
        assert wr.train_range == (0, 100)
        assert wr.eval_range == (100, 101)

    def test_window_result_is_frozen(self) -> None:
        """BTE-15: WindowResult is immutable."""
        ms = MetricSet(
            hit_rate=Decimal("0.50000000"),
            match_distribution={},
            average_matches=Decimal("0.50000000"),
            consistency_score=Decimal("0.50000000"),
            total_draws_evaluated=2,
        )
        wr = WindowResult(
            window_index=0,
            train_range=(0, 100),
            eval_range=(100, 101),
            strategy_metrics=ms,
            uniform_metrics=None,
            hypergeometric_metrics=None,
        )
        import pytest

        with pytest.raises(AttributeError):
            wr.window_index = 1  # type: ignore[misc]


class TestBacktestResult:
    """BacktestResult creation (BTE-10)."""

    def test_create_backtest_result(self) -> None:
        """Positive: BacktestResult created with all fields."""
        ms = MetricSet(
            hit_rate=Decimal("0.50000000"),
            match_distribution={},
            average_matches=Decimal("0.50000000"),
            consistency_score=Decimal("0.50000000"),
            total_draws_evaluated=2,
        )
        wr = WindowResult(
            window_index=0,
            train_range=(0, 100),
            eval_range=(100, 101),
            strategy_metrics=ms,
            uniform_metrics=None,
            hypergeometric_metrics=None,
        )
        result = BacktestResult(
            fingerprint="abc123",
            lottery_id=1,
            strategy_id="ml-core-5",
            status="active",
            aggregate_metrics=ms,
            window_history=(wr,),
            snapshot_id=1,
            version="1",
        )
        assert result.fingerprint == "abc123"
        assert result.status == "active"
        assert len(result.window_history) == 1


class TestDraw:
    """Draw creation."""

    def test_create_draw(self) -> None:
        """Positive: Draw created with required fields."""
        draw = Draw(
            id=1,
            draw_date=datetime(2024, 1, 1),
            numbers=(1, 2, 3, 4, 5),
            super_number=10,
        )
        assert draw.id == 1
        assert draw.numbers == (1, 2, 3, 4, 5)
        assert draw.super_number == 10

    def test_draw_is_frozen(self) -> None:
        """Draw is immutable."""
        draw = Draw(
            id=1,
            draw_date=datetime(2024, 1, 1),
            numbers=(1, 2, 3, 4, 5),
        )
        import pytest

        with pytest.raises(AttributeError):
            draw.id = 2  # type: ignore[misc]


class TestVersionConstant:
    """Version constant (BTE-06)."""

    def test_version_exists(self) -> None:
        """Positive: BACKTEST_GENERATOR_VERSION is importable."""
        assert BACKTEST_GENERATOR_VERSION is not None

    def test_version_is_string(self) -> None:
        """Positive: version is a string."""
        assert isinstance(BACKTEST_GENERATOR_VERSION, str)

    def test_version_format(self) -> None:
        """Positive: version follows semver-like format."""
        assert "." in BACKTEST_GENERATOR_VERSION
