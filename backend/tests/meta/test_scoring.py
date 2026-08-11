"""Tests for meta.scoring — weighted composite score computation.

Spec refs: META-001 (weighted scoring), META-019 (weight configuration).
Design refs: Scoring section.
"""

from __future__ import annotations

import pytest

from backend.app.meta.scoring import (
    DEFAULT_WEIGHTS,
    compute_score,
    validate_weights,
)


class TestDefaultWeights:
    """DEFAULT_WEIGHTS dict — META-001, META-019."""

    def test_sum_equals_one(self) -> None:
        total = sum(DEFAULT_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_contains_expected_keys(self) -> None:
        expected = {
            "hit_rate",
            "average_matches",
            "consistency_score",
            "precision",
            "recall",
        }
        assert set(DEFAULT_WEIGHTS.keys()) == expected

    def test_default_values(self) -> None:
        assert DEFAULT_WEIGHTS["hit_rate"] == 0.3
        assert DEFAULT_WEIGHTS["average_matches"] == 0.3
        assert DEFAULT_WEIGHTS["consistency_score"] == 0.2
        assert DEFAULT_WEIGHTS["precision"] == 0.1
        assert DEFAULT_WEIGHTS["recall"] == 0.1


class TestValidateWeights:
    """validate_weights — META-001."""

    def test_passes_for_nonzero_sum(self) -> None:
        validate_weights(DEFAULT_WEIGHTS)  # should not raise

    def test_rejects_zero_sum(self) -> None:
        zero_weights = {
            "hit_rate": 0.0,
            "average_matches": 0.0,
            "consistency_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
        }
        with pytest.raises(ValueError, match="sum"):
            validate_weights(zero_weights)

    def test_passes_for_negative_weights(self) -> None:
        """Negative weights are allowed as long as sum != 0."""
        weights = {
            "hit_rate": 0.5,
            "average_matches": 0.5,
            "consistency_score": -0.1,
            "precision": 0.0,
            "recall": 0.0,
        }
        validate_weights(weights)  # should not raise

    def test_passes_for_empty_dict(self) -> None:
        """Empty dict sums to 0 → raises."""
        with pytest.raises(ValueError, match="sum"):
            validate_weights({})


class TestComputeScore:
    """compute_score — weighted sum (META-001)."""

    def test_default_weights_computation(self) -> None:
        normalized = {
            "hit_rate": 0.8,
            "average_matches": 0.6,
            "consistency_score": 0.9,
            "precision": 0.7,
            "recall": 0.5,
        }
        score = compute_score(normalized, DEFAULT_WEIGHTS)
        expected = 0.8 * 0.3 + 0.6 * 0.3 + 0.9 * 0.2 + 0.7 * 0.1 + 0.5 * 0.1
        assert score == pytest.approx(expected)

    def test_custom_weights(self) -> None:
        normalized = {
            "hit_rate": 1.0,
            "average_matches": 0.0,
            "consistency_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
        }
        weights = {
            "hit_rate": 1.0,
            "average_matches": 0.0,
            "consistency_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
        }
        score = compute_score(normalized, weights)
        assert score == pytest.approx(1.0)

    def test_missing_metric_contributes_zero(self) -> None:
        """Missing metric from normalized → contributes 0.0 to score (META-002)."""
        normalized = {
            "hit_rate": 1.0,
            # missing other metrics
        }
        score = compute_score(normalized, DEFAULT_WEIGHTS)
        # Only hit_rate contributes: 1.0 * 0.3 = 0.3
        assert score == pytest.approx(0.3)

    def test_all_zero_metrics(self) -> None:
        normalized = {
            "hit_rate": 0.0,
            "average_matches": 0.0,
            "consistency_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
        }
        score = compute_score(normalized, DEFAULT_WEIGHTS)
        assert score == pytest.approx(0.0)

    def test_weights_with_extra_keys_ignored(self) -> None:
        """Weights dict with extra keys beyond metrics → those keys ignored."""
        normalized = {
            "hit_rate": 1.0,
            "average_matches": 0.0,
            "consistency_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
        }
        weights = {
            "hit_rate": 1.0,
            "average_matches": 0.0,
            "consistency_score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "extra_metric": 0.5,  # no matching metric
        }
        score = compute_score(normalized, weights)
        assert score == pytest.approx(1.0)
