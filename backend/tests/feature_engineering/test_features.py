"""Feature compute scenario tests (FE-01..FE-10, design §6/P1-01).

Each of the ten Core-Domain base features is validated against its spec scenario using a
pure ``FeatureContext``. Asserts a SPECIFIC expected value (never a tautology) and that
results are deterministic across calls. All values are INTEGER/Decimal (no float).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.feature_engineering.context import DrawRow, FeatureContext, LotteryRules
from backend.app.feature_engineering.features.base import draw_mean, draw_range, draw_sum
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

RULES = LotteryRules(min_number=1, max_number=45, numbers_to_select=5)


def _ctx(numbers: tuple[int, ...], draws: tuple[DrawRow, ...] | None = None) -> FeatureContext:
    row = DrawRow(draw_number=len(draws) if draws else 0, numbers=numbers)
    return FeatureContext(draw=row, draws=draws or (row,), rules=RULES)


def test_fe01_draw_sum() -> None:
    assert draw_sum(_ctx((1, 4, 7))) == 12


def test_fe02_draw_mean_is_exact_decimal() -> None:
    assert draw_mean(_ctx((1, 4, 7))) == Decimal(4)
    assert isinstance(draw_mean(_ctx((1, 4, 7))), Decimal)


def test_fe03_draw_range() -> None:
    assert draw_range(_ctx((5, 3, 8))) == 5


def test_fe04_odd_even_ratio() -> None:
    assert odd_even_ratio(_ctx((2, 3, 5, 8))) == Decimal(1)


def test_fe05_low_high_ratio_rule_derived_mid() -> None:
    assert low_high_ratio(_ctx((1, 44))) == Decimal(1)


def test_fe06_consecutive_count() -> None:
    assert consecutive_count(_ctx((5, 6, 12))) == 1


def test_fe07_decade_distribution() -> None:
    assert decade_distribution(_ctx((7, 15, 42))) == {1: 1, 11: 1, 41: 1}


def test_fe08_repeated_from_previous() -> None:
    draws = (
        DrawRow(draw_number=9, numbers=(3, 7, 44)),
        DrawRow(draw_number=10, numbers=(3, 9, 44)),
    )
    ctx = _ctx((3, 9, 44), draws)
    assert repeated_from_previous(ctx) == 2


def test_fe09_max_current_gap_never_seen() -> None:
    # Number 7 never appears by draw 12 -> gap measured from first draw (12 - 1 = 11).
    draws = tuple(DrawRow(draw_number=n, numbers=(1, 2)) for n in range(1, 13))
    ctx = FeatureContext(draw=DrawRow(12, (1, 2)), draws=draws, rules=RULES)
    assert max_current_gap(ctx) == 11


def test_fe10_current_frequency_cumulative() -> None:
    draws = (DrawRow(1, (1, 7)), DrawRow(4, (7, 9)), DrawRow(9, (7, 11)))
    ctx = FeatureContext(draw=draws[-1], draws=draws, rules=RULES)
    counts = current_frequency(ctx)
    assert counts[7] == 3


def test_all_features_are_deterministic_across_calls() -> None:
    fns = [
        draw_sum,
        draw_mean,
        draw_range,
        odd_even_ratio,
        low_high_ratio,
        consecutive_count,
        decade_distribution,
    ]
    ctx = _ctx((1, 2, 3, 44))
    for fn in fns:
        assert fn(ctx) == fn(ctx), f"{fn.__name__} is not deterministic"
