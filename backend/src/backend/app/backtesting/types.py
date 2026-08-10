"""Backtesting engine domain types (design Types, BTE-01/08/15).

Immutable dataclasses for backtest configuration, metrics, and results.
All metric values are Decimal(20,8) quantized (BTE-08).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class DrawContext:
    """Context for a single draw evaluation point (BTE-03).

    ``historical_draws`` is an expanding window containing only draws
    available at the evaluation point -- no future data (BTE-17).
    """

    lottery_id: int
    draw_date: datetime
    historical_draws: tuple[Draw, ...]
    feature_set: dict | None = None


@dataclass(frozen=True)
class BacktestConfig:
    """Walk-forward configuration (BTE-04, BTE-18).

    Parameters that affect reproducibility are included in the fingerprint.
    """

    train_years: int = 5
    eval_count: int = 1
    step_count: int = 1
    min_train_draws: int = 100
    seed: int = 42
    benchmark_type: str = "both"  # "uniform" | "hypergeometric" | "both"


@dataclass(frozen=True)
class MetricSet:
    """Lottery-specific metrics (BTE-08).

    All values are Decimal(20,8) quantized.
    """

    hit_rate: Decimal
    match_distribution: dict[int, int]
    average_matches: Decimal
    consistency_score: Decimal
    total_draws_evaluated: int


@dataclass(frozen=True)
class WindowResult:
    """Result of a single walk-forward window (BTE-15)."""

    window_index: int
    train_range: tuple[int, int]  # (start_idx, end_idx)
    eval_range: tuple[int, int]
    strategy_metrics: MetricSet
    uniform_metrics: MetricSet | None
    hypergeometric_metrics: MetricSet | None


@dataclass(frozen=True)
class BacktestResult:
    """Full backtest result (BTE-10)."""

    fingerprint: str
    lottery_id: int
    strategy_id: str
    status: str  # "active" | "retired" | "failed"
    aggregate_metrics: MetricSet
    window_history: tuple[WindowResult, ...]
    snapshot_id: int | None = None
    version: str | None = None


@dataclass(frozen=True)
class Draw:
    """Minimal draw representation for walk-forward splitting."""

    id: int
    draw_date: datetime
    numbers: tuple[int, ...]
    super_number: int | None = None
