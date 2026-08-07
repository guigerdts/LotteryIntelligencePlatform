"""Parity-based counters and adjacency counts (FE-04, FE-06).

Pure integer counting over a draw's numbers; results are exact INTEGER ratios/counts
(FES-05).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.feature_engineering.context import FeatureContext


def odd_even_ratio(ctx: FeatureContext) -> Decimal:
    """FE-04: ``odd count : even count`` as an exact Decimal ratio.

    Scenario FE-04: ``[2, 3, 5, 8]`` -> 2 odds : 2 evens = 1. An all-even or all-odd draw
    is reported as the corresponding integer (never ``ZeroDivisionError``); the ratio is
    always represented as a Decimal regardless of divisibility.
    """
    odd = sum(1 for n in ctx.draw.numbers if n % 2 == 1)
    even = len(ctx.draw.numbers) - odd
    if even == 0:
        return Decimal(odd) if odd else Decimal(0)
    return Decimal(odd) / Decimal(even)


def consecutive_count(ctx: FeatureContext) -> int:
    """FE-06: number of adjacent (difference-1) pairs within sorted numbers.

    Scenario FE-06: ``[5, 6, 12]`` -> 1 (the 5-6 pair); 6-12 is not adjacent.
    """
    sorted_numbers = sorted(ctx.draw.numbers)
    return sum(
        1 for i in range(len(sorted_numbers) - 1) if sorted_numbers[i + 1] - sorted_numbers[i] == 1
    )
