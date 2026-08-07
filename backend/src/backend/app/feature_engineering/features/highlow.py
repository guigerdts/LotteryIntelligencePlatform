"""Low/high ratio against the rule-derived mid (FE-05).

Uses the lottery rules' ``min_number``/``max_number`` to derive a mid band; numbers at or
below the mid are ``low``. Pure INTEGER input, Decimal ratio output (FES-05).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.feature_engineering.context import FeatureContext


def low_high_ratio(ctx: FeatureContext) -> Decimal:
    """FE-05: ratio of numbers below/above the rule-derived mid.

    Scenario FE-05: ``min=1, max=45``, numbers ``[1, 44]`` -> mid=23 from rules, 1 low : 1
    high -> ``1.0``. A numbers_to_select total with no counterpart returns the integer.
    """
    if ctx.rules is None:
        return Decimal(0)
    numbers = ctx.draw.numbers
    if not numbers:
        return Decimal(0)
    mid = (ctx.rules.min_number + ctx.rules.max_number) // 2
    low = sum(1 for n in numbers if n <= mid)
    high = len(numbers) - low
    if high == 0:
        return Decimal(low)
    return Decimal(low) / Decimal(high)
