"""Weighted scoring for Meta Learning module.

Computes composite score per model snapshot using weighted sum of
normalized metrics (META-001). Default weights are global, overridable
per-lottery via config_json (META-019).
"""

from __future__ import annotations

# Default weights (META-001, META-019).
DEFAULT_WEIGHTS: dict[str, float] = {
    "hit_rate": 0.3,
    "average_matches": 0.3,
    "consistency_score": 0.2,
    "precision": 0.1,
    "recall": 0.1,
}


def validate_weights(weights: dict[str, float]) -> None:
    """Reject zero-sum weights (META-001).

    Raises ValueError if weights sum to zero.
    """
    total = sum(weights.values())
    if total == 0.0:
        raise ValueError("Weights must not sum to zero")


def compute_score(normalized_metrics: dict[str, float], weights: dict[str, float]) -> float:
    """Compute weighted composite score (META-001).

    Formula: score = Σ(normalized_metric × weight) for metrics present
    in both the normalized_metrics and weights dicts. Missing metrics
    contribute 0.0 to the score.
    """
    score = 0.0
    for metric, weight in weights.items():
        value = normalized_metrics.get(metric, 0.0)
        score += value * weight
    return score
