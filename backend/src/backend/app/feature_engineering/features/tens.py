"""Decade (tens) distribution feature (FE-07).

Buckets each draw's numbers into per-decade bands (`1-10, 11-20, 21-30, 31-40, 41-max`)
derived from the lottery ``max_number``. Returns a deterministic Mapping keyed by band
start so JSON stays canonical (FES-05). Pure INTEGER counts.
"""

from __future__ import annotations

from collections import defaultdict

from backend.app.feature_engineering.context import FeatureContext


def decade_distribution(ctx: FeatureContext) -> dict[int, int]:
    """FE-07: per-decade-band counts.

    Scenario FE-07: numbers ``[7, 15, 42]`` with ``max=45`` -> ``{1: 1, 11: 1, 41: 1}``
    (1-10:1, 11-20:1, 41-45:1). Every number past 10 is assigned to its ``((n-1)//10)*10+1``
    band; a last open band (41..max) naturally emerges from the decade buckets.
    """
    if not ctx.draw.numbers:
        return {}
    buckets: dict[int, int] = defaultdict(int)
    for n in ctx.draw.numbers:
        band_start = ((n - 1) // 10) * 10 + 1
        buckets[band_start] += 1
    return dict(sorted(buckets.items()))
