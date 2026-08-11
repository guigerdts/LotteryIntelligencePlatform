"""Tests for meta.normalization — per-engine min-max normalization.

Spec refs: META-002 (cross-engine normalization), META-004 (failed run exclusion).
Design refs: Cross-Engine Normalization section.
"""

from __future__ import annotations

import pytest

from backend.app.meta.normalization import (
    COMMON_METRICS,
    ENGINE_EXCLUDED,
    normalize_per_engine,
)


class TestCommonMetrics:
    """COMMON_METRICS list — META-002."""

    def test_contains_expected_metrics(self) -> None:
        expected = {
            "hit_rate",
            "average_matches",
            "consistency_score",
            "precision",
            "recall",
            "f1_score",
        }
        assert set(COMMON_METRICS) == expected

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            COMMON_METRICS.append("new_metric")  # type: ignore[attr-defined]


class TestEngineExcluded:
    """ENGINE_EXCLUDED set — META-002."""

    def test_contains_best_fitness(self) -> None:
        assert "best_fitness" in ENGINE_EXCLUDED

    def test_contains_total_draws_evaluated(self) -> None:
        assert "total_draws_evaluated" in ENGINE_EXCLUDED

    def test_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            ENGINE_EXCLUDED.add("new_metric")  # type: ignore[attr-defined]


class TestNormalizePerEngine:
    """normalize_per_engine — per-engine min-max normalization (META-002)."""

    def test_single_engine_two_snapshots(self) -> None:
        snapshots = [
            {"engine_type": "ml", "model_id": "a", "hit_rate": 0.4, "precision": 0.6},
            {"engine_type": "ml", "model_id": "b", "hit_rate": 0.8, "precision": 0.2},
        ]
        result = normalize_per_engine(snapshots)
        # hit_rate: min=0.4, max=0.8 → (0.4-0.4)/(0.8-0.4)=0.0, (0.8-0.4)/(0.8-0.4)=1.0
        assert result[0]["hit_rate"] == pytest.approx(0.0)
        assert result[1]["hit_rate"] == pytest.approx(1.0)
        # precision: min=0.2, max=0.6 → (0.6-0.2)/(0.6-0.2)=1.0, (0.2-0.2)/(0.6-0.2)=0.0
        assert result[0]["precision"] == pytest.approx(1.0)
        assert result[1]["precision"] == pytest.approx(0.0)

    def test_cross_engine_independence(self) -> None:
        """ML and BT engines normalize independently (META-002)."""
        snapshots = [
            {"engine_type": "ml", "model_id": "a", "hit_rate": 0.5},
            {"engine_type": "ml", "model_id": "b", "hit_rate": 1.0},
            {"engine_type": "backtesting", "model_id": "c", "hit_rate": 0.1},
            {"engine_type": "backtesting", "model_id": "d", "hit_rate": 0.2},
        ]
        result = normalize_per_engine(snapshots)
        ml_scores = [r["hit_rate"] for r in result if r["engine_type"] == "ml"]
        bt_scores = [r["hit_rate"] for r in result if r["engine_type"] == "backtesting"]
        # ML: 0.5→0.0, 1.0→1.0
        assert ml_scores == [pytest.approx(0.0), pytest.approx(1.0)]
        # BT: 0.1→0.0, 0.2→1.0
        assert bt_scores == [pytest.approx(0.0), pytest.approx(1.0)]

    def test_constant_values_become_zero(self) -> None:
        """Constant values within an engine → 0.0 (META-002)."""
        snapshots = [
            {"engine_type": "ml", "model_id": "a", "hit_rate": 0.5},
            {"engine_type": "ml", "model_id": "b", "hit_rate": 0.5},
        ]
        result = normalize_per_engine(snapshots)
        assert result[0]["hit_rate"] == 0.0
        assert result[1]["hit_rate"] == 0.0

    def test_missing_metric_becomes_zero(self) -> None:
        """Missing metric → 0.0 (conservative, META-002)."""
        snapshots = [
            {"engine_type": "ml", "model_id": "a", "hit_rate": 0.8},
            {"engine_type": "ml", "model_id": "b", "hit_rate": 0.4, "precision": 0.7},
        ]
        result = normalize_per_engine(snapshots)
        # First snapshot missing precision → 0.0
        assert result[0]["precision"] == 0.0
        # Second snapshot has precision
        assert result[1]["precision"] == pytest.approx(1.0)

    def test_excluded_metrics_not_normalized(self) -> None:
        """Engine-excluded metrics pass through unchanged (META-002)."""
        snapshots = [
            {"engine_type": "optimization", "model_id": "a", "hit_rate": 0.5, "best_fitness": 0.95},
            {"engine_type": "optimization", "model_id": "b", "hit_rate": 0.8, "best_fitness": 0.80},
        ]
        result = normalize_per_engine(snapshots)
        # hit_rate is common → normalized
        assert result[0]["hit_rate"] == pytest.approx(0.0)
        assert result[1]["hit_rate"] == pytest.approx(1.0)
        # best_fitness is excluded → passes through unchanged
        assert result[0]["best_fitness"] == 0.95
        assert result[1]["best_fitness"] == 0.80

    def test_consistency_score_inversion(self) -> None:
        """consistency_score inverted: lower raw → higher normalized (META-002)."""
        snapshots = [
            {"engine_type": "ml", "model_id": "a", "consistency_score": 10.0},
            {"engine_type": "ml", "model_id": "b", "consistency_score": 20.0},
        ]
        result = normalize_per_engine(snapshots)
        # Raw: a=10 (better), b=20 (worse) — lower is better for consistency
        # After inversion: a should be higher than b
        assert result[0]["consistency_score"] > result[1]["consistency_score"]
        # Check that inversion preserves relative ordering
        assert result[0]["consistency_score"] == pytest.approx(1.0)
        assert result[1]["consistency_score"] == pytest.approx(0.0)

    def test_single_snapshot_normalization(self) -> None:
        """Single snapshot in engine → normalized to 1.0 (best available)."""
        snapshots = [
            {"engine_type": "ml", "model_id": "a", "hit_rate": 0.8},
        ]
        result = normalize_per_engine(snapshots)
        assert result[0]["hit_rate"] == 1.0

    def test_empty_snapshots(self) -> None:
        """Empty list returns empty list."""
        result = normalize_per_engine([])
        assert result == []

    def test_preserves_extra_fields(self) -> None:
        """Non-metric fields (model_id, engine_type) preserved."""
        snapshots = [
            {"engine_type": "ml", "model_id": "ml-core-5", "hit_rate": 0.8, "custom_field": "x"},
        ]
        result = normalize_per_engine(snapshots)
        assert result[0]["model_id"] == "ml-core-5"
        assert result[0]["engine_type"] == "ml"
        assert result[0]["custom_field"] == "x"
