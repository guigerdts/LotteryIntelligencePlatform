"""Statistics engine determinism tests (G9 intro, C2/STE-05).

Proves the pure metric engines are deterministic: identical input yields
byte-identical output for every metric family (frequency, positional frequency,
gaps, NULL-aware averages, and base-2 entropy). This is the PR1 engine-output
determinism gate; the authoritative two-independent-generations G9 assertion on
a migrated DB ships with PR2.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.statistics.engine import (
    entropy_base2,
    frequency,
    gaps,
    null_aware_average,
    positional_frequency,
)

# Two draws' numbers, in ascending draw_number / position order.
NUM_DRAWS = [[1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 6, 7, 8, 9]]


def test_frequency_is_int_exact_and_deterministic() -> None:
    first = frequency(NUM_DRAWS)
    second = frequency(NUM_DRAWS)
    assert first == second
    assert first == {1: 2, 2: 2, 3: 2, 4: 1, 5: 1, 6: 2, 7: 2, 8: 1, 9: 1}
    assert all(isinstance(count, int) for count in first.values())


def test_frequency_folds_to_same_counts_regardless_of_draw_order() -> None:
    # Same multiset of drawn numbers in a different draw order folds to the same
    # counts (counters are order-independent).
    assert frequency(reversed(NUM_DRAWS)) == frequency(NUM_DRAWS)


def test_positional_frequency_deterministic() -> None:
    first = positional_frequency(NUM_DRAWS)
    second = positional_frequency(NUM_DRAWS)
    assert first == second
    # Number 1 sits at position 1 in both draws.
    assert first[(1, 1)] == 2
    # Number 7 sits at position 7 in the first draw and position 5 in the second.
    assert first[(7, 7)] == 1
    assert first[(7, 5)] == 1
    assert all(isinstance(count, int) for count in first.values())


def test_gaps_zero_default_and_exact_average() -> None:
    # Numbers that reappear across the two draws do so one draw apart (gap==1);
    # numbers appearing only once (4, 5, 8, 9) get a zero-gap summary.
    result = gaps(NUM_DRAWS)
    assert result[2].count == 1
    assert result[2].min_gap == 1
    assert result[2].max_gap == 1
    assert result[2].avg_gap == Decimal(1)
    assert result[8].count == 0
    assert result[8].min_gap is None
    assert result[8].max_gap is None
    assert result[8].avg_gap is None
    assert gaps(NUM_DRAWS) == result


def test_null_aware_average_ignores_nulls_without_imputing() -> None:
    assert null_aware_average([Decimal(10), None, Decimal(20)]) == Decimal(15)
    assert null_aware_average([None, None]) is None
    assert null_aware_average([Decimal(25)]) == Decimal(25)


def test_entropy_uniform_is_bits_of_universe_size() -> None:
    # Four equiprobable numbers over [1..4] -> entropy == 2 bits.
    counts = {1: 1, 2: 1, 3: 1, 4: 1}
    assert entropy_base2(counts, 1, 4) == Decimal("2.000000")


def test_entropy_deterministic_and_universe_bounded() -> None:
    counts = {1: 3, 2: 1}
    first = entropy_base2(counts, 1, 2)
    second = entropy_base2(counts, 1, 2)
    assert first == second
    # p(1)=3/4, p(2)=1/4 -> H = 0.75*log2(4/3) + 0.25*log2(4) ~ 0.811278.
    assert first == Decimal("0.811278")
    # Zero-appearance numbers over a wider universe contribute 0 and do not
    # change the entropy for the same observed counts.
    assert entropy_base2(counts, 1, 4) == first


def test_entropy_empty_returns_zero() -> None:
    assert entropy_base2({}, 1, 5) == Decimal(0)
