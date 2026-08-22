"""Canonical feature contract for the ML engine (MLE-03/05, design M-A5).

``ML_FEATURE_ORDER`` is the fixed column order of the design matrix ``X``: the 8
F4 Core-Domain features whose computed values persist as scalar cells in
``feature_values`` — exactly what the F4 service ``_build_rows`` stores after its
``SIMPLE_SCALAR_TYPES`` filter (design §2/FES-05). The two mapping-valued Core
features, FE-07 ``decade_distribution`` and FE-10 ``current_frequency``, are
computed and fingerprinted by F4 but carry NO persisted cell, so they stay out
of the training contracts until persistence supports non-scalar values; the
matrix builder raises on absence rather than zero-guessing (MLE-06). The order
is part of the fingerprint contract — a reordering would break determinism
(MLE-05). The contract test pins the exact literal tuple; it intentionally does
NOT compare dynamically against ``build_feature_registry()``, which also holds
non-persistable ids.
"""

from __future__ import annotations

from typing import Final

# The 8 scalar-persistable F4 feature ids (FE-01..FE-06, FE-08, FE-09) in
# canonical sorted order (M-A5, aligned with F4 persistence reality).
ML_FEATURE_ORDER: Final[tuple[str, ...]] = (
    "consecutive_count",
    "draw_mean",
    "draw_range",
    "draw_sum",
    "low_high_ratio",
    "max_current_gap",
    "odd_even_ratio",
    "repeated_from_previous",
)

__all__ = ["ML_FEATURE_ORDER"]
