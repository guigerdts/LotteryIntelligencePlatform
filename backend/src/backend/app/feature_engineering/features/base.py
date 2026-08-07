"""Per-draw arithmetic features: sum, mean, range (FE-01..FE-03).

Pure functions over a single draw's ``numbers``; INTEGER/Decimal-exact so any two runs
over identical draws fold to identical values (FES-05).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.feature_engineering.context import FeatureContext


def draw_sum(ctx: FeatureContext) -> int:
    """FE-01: exact integer sum of a draw's numbers.

    Scenario FE-01: ``[1, 4, 7]`` -> 12 for that ``draw_number``.
    """
    return sum(ctx.draw.numbers)


def draw_mean(ctx: FeatureContext) -> Decimal:
    """FE-02: exact Decimal mean of a draw's numbers (never float).

    Division is performed by ``Decimal``/``int`` to keep the accumulator exact. Scenario
    FE-02: ``[1, 4, 7]`` with ``numbers_to_select=3`` -> ``Decimal(4)``.
    """
    count = len(ctx.draw.numbers)
    if count == 0:
        return Decimal(0)
    total = Decimal(sum(ctx.draw.numbers))
    return total / Decimal(count)


def draw_range(ctx: FeatureContext) -> int:
    """FE-03: ``max - min`` of a draw's numbers.

    Scenario FE-03: ``[5, 3, 8]`` -> 5 (8 - 3).
    """
    if not ctx.draw.numbers:
        return 0
    return max(ctx.draw.numbers) - min(ctx.draw.numbers)
