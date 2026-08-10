"""Lottery-specific metrics calculator and aggregation (BTE-08, BTE-15).

Provides ``LotteryMetrics.compute`` for per-window metric calculation
and ``LotteryMetrics.aggregate`` for weighted cross-window aggregation.
All values are Decimal(20,8) quantized (BTE-08).
"""

from __future__ import annotations

import math
from collections import Counter
from decimal import Decimal

from backend.app.backtesting.determinism import quantize_metric
from backend.app.backtesting.types import MetricSet


class LotteryMetrics:
    """Lottery-specific metrics calculator (BTE-08).

    All public methods are ``@staticmethod`` — no instance state.
    Every metric value is quantized to ``Decimal(20,8)``.
    """

    @staticmethod
    def compute(
        predictions: list[list[int]],
        actuals: list[list[int]],
        k_threshold: int = 1,
    ) -> MetricSet:
        """Compute metrics for *predictions* vs *actuals*.

        Parameters:
            predictions: List of predicted number sets (one per draw).
            actuals: List of actual winning number sets (one per draw).
            k_threshold: Minimum matches to count as a "hit" (default 1).

        Returns:
            ``MetricSet`` with all values Decimal(20,8).

        Raises:
            ValueError: If *predictions* and *actuals* have different lengths,
                or either list is empty.
        """
        if len(predictions) != len(actuals):
            raise ValueError(
                f"predictions ({len(predictions)}) and actuals ({len(actuals)}) "
                "must have the same length"
            )
        if not predictions:
            raise ValueError("predictions and actuals must not be empty")

        match_counts = [
            LotteryMetrics._count_matches(p, a) for p, a in zip(predictions, actuals, strict=True)
        ]

        total = len(match_counts)
        hits = sum(1 for m in match_counts if m >= k_threshold)
        hit_rate = Decimal(hits) / Decimal(total)

        distribution: Counter[int] = Counter(match_counts)
        match_distribution = dict(sorted(distribution.items()))

        avg = sum(match_counts) / total
        variance = sum((m - avg) ** 2 for m in match_counts) / total
        stddev = math.sqrt(float(variance))

        return MetricSet(
            hit_rate=quantize_metric(hit_rate),
            match_distribution=match_distribution,
            average_matches=quantize_metric(avg),
            consistency_score=quantize_metric(stddev),
            total_draws_evaluated=total,
        )

    @staticmethod
    def aggregate(window_metrics: list[MetricSet]) -> MetricSet:
        """Aggregate per-window metrics weighted by ``total_draws_evaluated``.

        Parameters:
            window_metrics: One ``MetricSet`` per walk-forward window.

        Returns:
            Single ``MetricSet`` representing the weighted aggregate.

        Raises:
            ValueError: If *window_metrics* is empty.
        """
        if not window_metrics:
            raise ValueError("window_metrics must not be empty")

        total_draws = sum(m.total_draws_evaluated for m in window_metrics)
        if total_draws == 0:
            raise ValueError("total_draws_evaluated across windows must be > 0")

        # Weighted average of hit_rate
        wr_hit = sum(m.hit_rate * m.total_draws_evaluated for m in window_metrics) / Decimal(
            total_draws
        )

        # Merge match distributions
        merged_dist: Counter[int] = Counter()
        for m in window_metrics:
            for k, v in m.match_distribution.items():
                merged_dist[k] += v
        match_distribution = dict(sorted(merged_dist.items()))

        # Weighted average of average_matches
        wr_avg = sum(m.average_matches * m.total_draws_evaluated for m in window_metrics) / Decimal(
            total_draws
        )

        # Pooled consistency (weighted RMS of per-window stddev)
        import math

        wr_var = (
            sum(float(m.consistency_score) ** 2 * m.total_draws_evaluated for m in window_metrics)
            / total_draws
        )
        wr_stddev = math.sqrt(wr_var)

        return MetricSet(
            hit_rate=quantize_metric(wr_hit),
            match_distribution=match_distribution,
            average_matches=quantize_metric(wr_avg),
            consistency_score=quantize_metric(wr_stddev),
            total_draws_evaluated=total_draws,
        )

    @staticmethod
    def _count_matches(predicted: list[int], actual: list[int]) -> int:
        """Count matching numbers between *predicted* and *actual*."""
        return len(set(predicted) & set(actual))
