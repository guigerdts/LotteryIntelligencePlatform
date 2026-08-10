"""Tests for LotteryMetrics compute and aggregate (BTE-08, BTE-15).

Verifies calculation accuracy, Decimal quantisation, determinism,
aggregation, and edge cases.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.backtesting.metrics import LotteryMetrics
from backend.app.backtesting.types import MetricSet


class TestLotteryMetricsCompute:
    """Per-window metric calculation (BTE-08)."""

    def test_exact_matches(self) -> None:
        """All predictions match exactly."""
        preds = [[1, 2, 3], [4, 5, 6]]
        actuals = [[1, 2, 3], [4, 5, 6]]
        ms = LotteryMetrics.compute(preds, actuals, k_threshold=1)
        assert ms.hit_rate == Decimal("1.00000000")
        assert ms.average_matches == Decimal("3.00000000")
        assert ms.total_draws_evaluated == 2

    def test_zero_matches(self) -> None:
        """No predictions match."""
        preds = [[1, 2, 3], [4, 5, 6]]
        actuals = [[7, 8, 9], [10, 11, 12]]
        ms = LotteryMetrics.compute(preds, actuals, k_threshold=1)
        assert ms.hit_rate == Decimal("0.00000000")
        assert ms.average_matches == Decimal("0.00000000")

    def test_partial_matches(self) -> None:
        """Mixed match counts."""
        preds = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        actuals = [[1, 2, 10], [4, 5, 10], [10, 11, 12]]
        ms = LotteryMetrics.compute(preds, actuals, k_threshold=1)
        assert ms.hit_rate == Decimal("0.66666667")  # 2/3
        assert ms.average_matches == Decimal("1.33333333")  # (2+2+0)/3
        assert ms.total_draws_evaluated == 3

    def test_match_distribution(self) -> None:
        """Distribution histogram is correct."""
        preds = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [1, 5, 9]]
        actuals = [[1, 2, 3], [4, 5, 10], [10, 11, 12], [1, 5, 10]]
        ms = LotteryMetrics.compute(preds, actuals, k_threshold=1)
        # matches: 3, 2, 0, 2
        assert ms.match_distribution == {0: 1, 2: 2, 3: 1}

    def test_k_threshold(self) -> None:
        """Hit rate respects k_threshold."""
        preds = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        actuals = [[1, 2, 10], [4, 10, 11], [10, 11, 12]]
        ms1 = LotteryMetrics.compute(preds, actuals, k_threshold=1)
        ms2 = LotteryMetrics.compute(preds, actuals, k_threshold=2)
        # k=1: 2 hits (2+1 matches); k=2: 1 hit (only first draw)
        assert ms1.hit_rate == Decimal("0.66666667")
        assert ms2.hit_rate == Decimal("0.33333333")

    def test_decimal_precision(self) -> None:
        """All metric values are Decimal(20,8)."""
        preds = [[1, 2, 3]]
        actuals = [[1, 2, 3]]
        ms = LotteryMetrics.compute(preds, actuals)
        assert isinstance(ms.hit_rate, Decimal)
        assert isinstance(ms.average_matches, Decimal)
        assert isinstance(ms.consistency_score, Decimal)

    def test_consistency_score_zero_when_identical(self) -> None:
        """Consistency score is 0 when all draws have same match count."""
        preds = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        actuals = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        ms = LotteryMetrics.compute(preds, actuals)
        assert ms.consistency_score == Decimal("0.00000000")

    def test_deterministic(self) -> None:
        """Same inputs produce identical MetricSet."""
        preds = [[1, 2, 3], [4, 5, 6]]
        actuals = [[1, 2, 10], [4, 10, 11]]
        ms1 = LotteryMetrics.compute(preds, actuals)
        ms2 = LotteryMetrics.compute(preds, actuals)
        assert ms1 == ms2


class TestLotteryMetricsEdgeCases:
    """Edge cases and error handling."""

    def test_empty_predictions_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            LotteryMetrics.compute([], [])

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            LotteryMetrics.compute([[1, 2, 3]], [[1, 2, 3], [4, 5, 6]])

    def test_single_draw(self) -> None:
        ms = LotteryMetrics.compute([[1, 2, 3]], [[1, 2, 3]])
        assert ms.total_draws_evaluated == 1
        assert ms.hit_rate == Decimal("1.00000000")


class TestLotteryMetricsAggregate:
    """Weighted aggregation across windows (BTE-15)."""

    def _ms(
        self,
        hit_rate: str,
        avg: str,
        consistency: str,
        total: int,
        dist: dict[int, int] | None = None,
    ) -> MetricSet:
        return MetricSet(
            hit_rate=Decimal(hit_rate),
            match_distribution=dist or {},
            average_matches=Decimal(avg),
            consistency_score=Decimal(consistency),
            total_draws_evaluated=total,
        )

    def test_single_window_passthrough(self) -> None:
        ms = self._ms("0.50000000", "1.50000000", "0.50000000", 10)
        agg = LotteryMetrics.aggregate([ms])
        assert agg.hit_rate == Decimal("0.50000000")
        assert agg.average_matches == Decimal("1.50000000")
        assert agg.total_draws_evaluated == 10

    def test_weighted_average(self) -> None:
        m1 = self._ms("0.80000000", "2.00000000", "0.40000000", 100)
        m2 = self._ms("0.40000000", "1.00000000", "0.60000000", 50)
        agg = LotteryMetrics.aggregate([m1, m2])
        # hit_rate: (0.8*100 + 0.4*50) / 150 = 100/150 = 0.66666667
        assert agg.hit_rate == Decimal("0.66666667")
        assert agg.total_draws_evaluated == 150

    def test_merge_distributions(self) -> None:
        m1 = self._ms("0.50000000", "1.00000000", "0.50000000", 10, {0: 5, 1: 5})
        m2 = self._ms("0.50000000", "1.00000000", "0.50000000", 10, {1: 3, 2: 7})
        agg = LotteryMetrics.aggregate([m1, m2])
        assert agg.match_distribution == {0: 5, 1: 8, 2: 7}

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            LotteryMetrics.aggregate([])

    def test_zero_total_draws_raises(self) -> None:
        ms = self._ms("0.50000000", "1.00000000", "0.50000000", 0)
        with pytest.raises(ValueError, match="must be > 0"):
            LotteryMetrics.aggregate([ms])
