"""Cross-engine normalization for Meta Learning module.

Per-engine min-max normalization of common metrics (META-002).
Engine-specific metrics are excluded from cross-engine ranking.
Missing metrics default to 0.0 (conservative). Consistency score is
inverted (lower raw → higher normalized) before scoring.
"""

from __future__ import annotations

from typing import Any

# Common metrics that are comparable across engines (META-002).
COMMON_METRICS: tuple[str, ...] = (
    "hit_rate",
    "average_matches",
    "consistency_score",
    "precision",
    "recall",
    "f1_score",
)

# Engine-specific metrics excluded from cross-engine ranking (META-002).
ENGINE_EXCLUDED: frozenset[str] = frozenset({"best_fitness", "total_draws_evaluated"})


def _inverted_metrics() -> set[str]:
    """Metrics where lower raw value is better (inverted before normalization)."""
    return {"consistency_score"}


def normalize_per_engine(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize metrics per engine using min-max normalization (META-002).

    Within each engine_type, metrics are normalized to [0, 1] range.
    Constant values → 0.0. Missing metrics → 0.0 (conservative).
    Consistency score is inverted (lower raw → higher normalized).

    Returns a new list of dicts with normalized metric values. Non-metric
    fields (model_id, engine_type, etc.) are preserved as-is.
    """
    if not snapshots:
        return []

    # Group by engine_type
    engines: dict[str, list[int]] = {}
    for i, snap in enumerate(snapshots):
        et = snap.get("engine_type", "unknown")
        engines.setdefault(et, []).append(i)

    inverted = _inverted_metrics()
    result = [dict(s) for s in snapshots]

    for indices in engines.values():
        # Collect values for each common metric within this engine
        for metric in COMMON_METRICS:
            values = [snapshots[i].get(metric) for i in indices]
            numeric_values = [v for v in values if v is not None and metric not in ENGINE_EXCLUDED]

            if len(numeric_values) == 0:
                # No values at all → 0.0
                for idx in indices:
                    result[idx][metric] = 0.0
                continue

            if len(numeric_values) == 1:
                # Only one snapshot has this metric → 1.0 (best available)
                for i_pos, idx in enumerate(indices):
                    val = values[i_pos]
                    if val is None:
                        result[idx][metric] = 0.0
                    else:
                        result[idx][metric] = 1.0
                continue

            raw_min = min(numeric_values)
            raw_max = max(numeric_values)

            if raw_max == raw_min:
                # Constant values → 0.0
                for idx in indices:
                    result[idx][metric] = 0.0
                continue

            for i_pos, idx in enumerate(indices):
                val = values[i_pos]
                if val is None:
                    result[idx][metric] = 0.0
                    continue

                # Apply inversion for consistency_score
                if metric in inverted:
                    # Invert: lower raw → higher normalized
                    normalized = (raw_max - val) / (raw_max - raw_min)
                else:
                    normalized = (val - raw_min) / (raw_max - raw_min)

                result[idx][metric] = normalized

    return result
