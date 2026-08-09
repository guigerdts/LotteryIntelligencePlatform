"""Canonical feature contract for the ML engine (MLE-03/05, design M-A5).

``ML_FEATURE_ORDER`` is the fixed column order of the design matrix ``X``: the 10
base F4 Core-Domain feature ids in canonical sorted order (matching the F4 service
``_build_rows`` which persists ``sorted(execution.values)``). The order is part of the
fingerprint contract — a reordering would break determinism (MLE-05). The contract
test pins it exactly against the built F4 registry.
"""

from __future__ import annotations

from typing import Final

# The 10 base F4 feature ids (FE-01..FE-10) in canonical sorted order (M-A5).
# MUST stay in sync with the F4 registry: the contract test asserts tuple equality.
ML_FEATURE_ORDER: Final[tuple[str, ...]] = (
    "consecutive_count",
    "current_frequency",
    "decade_distribution",
    "draw_mean",
    "draw_range",
    "draw_sum",
    "low_high_ratio",
    "max_current_gap",
    "odd_even_ratio",
    "repeated_from_previous",
)

__all__ = ["ML_FEATURE_ORDER"]
