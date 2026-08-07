"""Pure per-feature ``compute(ctx)`` modules for the Core-Domain slice (FE-01..FE-10).

Each module exposes a pure ``compute(ctx: FeatureContext)`` returning an INTEGER/Decimal
value (or determiinistic mapping) with no side effects and no DB. Float never enters a
checksum or persisted value (FES-05). Modules are registered into the ``FeatureRegistry``
by the service layer (PR2) via a ``FeatureDefinition`` + this compute.
"""

from __future__ import annotations

from backend.app.feature_engineering.features.base import (
    draw_mean,
    draw_range,
    draw_sum,
)
from backend.app.feature_engineering.features.counters import (
    consecutive_count,
    odd_even_ratio,
)
from backend.app.feature_engineering.features.highlow import low_high_ratio
from backend.app.feature_engineering.features.tail import (
    current_frequency,
    max_current_gap,
    repeated_from_previous,
)
from backend.app.feature_engineering.features.tens import decade_distribution

__all__ = [
    "current_frequency",
    "consecutive_count",
    "decade_distribution",
    "draw_mean",
    "draw_range",
    "draw_sum",
    "low_high_ratio",
    "max_current_gap",
    "odd_even_ratio",
    "repeated_from_previous",
]
