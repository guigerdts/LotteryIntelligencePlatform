"""Pure, deterministic statistics metric engines (design §3 / §10).

Every function is a pure reduction over the raw drawn ``numbers`` values with no
DB I/O and no unordered float reduction. Accumulators are `INTEGER` counts or
`Decimal` means, so any two generations over the same input produce bit-identical
output (C2/STE-05). Input ``numbers`` is an iterable of draws, each draw being
the drawn main ``number`` values in ascending ``position`` order; the repository
layer supplies this already ordered deterministically (design §9 ORDER BY).

All arithmetic that can reach the snapshot checksum is `Decimal`-exact. Float is
never used in the entropy path (design §10).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, getcontext

# Working precision for Decimal entropy/mean arithmetic; high so that accumulators
# stay exact and the final quantization (below) is the only rounding point.
getcontext().prec = 40

_ENTROPY_PRECISION = Decimal("0.000001")
# Natural-log constant used as the common denominator for base-2 entropy steps.
_LOG2_DENOMINATOR = Decimal(2).ln()


@dataclass(frozen=True)
class GapSummary:
    """Per-number gap statistics over a draw range (STE-03)."""

    count: int
    min_gap: int | None
    max_gap: int | None
    avg_gap: Decimal | None


def frequency(numbers: Iterable[Iterable[int]]) -> dict[int, int]:
    """Count appearances of each drawn main ``number`` (exact INTEGER accumulator).

    Returns an insertion-ordered `dict[int, int]`; keys are sorted only if the
    caller iterates them — the counts themselves are exact.
    """
    counts: dict[int, int] = defaultdict(int)
    for draw in numbers:
        for number in draw:
            counts[number] += 1
    return dict(counts)


def positional_frequency(numbers: Iterable[Iterable[int]]) -> dict[tuple[int, int], int]:
    """Count ``(number, position)`` pairs across draws (INTEGER accumulator).

    ``position`` is the 1-based index within each draw (design §2 freq_positions).
    """
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for draw in numbers:
        for position, number in enumerate(draw, start=1):
            counts[(number, position)] += 1
    return dict(counts)


def gaps(numbers: Iterable[Iterable[int]]) -> dict[int, GapSummary]:
    """Per-number gap summary computed from a last-seen (STE-03).

    For each ``number`` the gap series is the difference (in draws) between
    consecutive appearances. ``count`` is the number of gaps observed; a number
    that appears only once (or never) yields ``count=0`` with ``None`` stats.
    """
    last_seen: dict[int, int] = {}
    per_number: dict[int, list[int]] = defaultdict(list)
    for index, draw in enumerate(numbers):
        for number in draw:
            if number in last_seen:
                per_number[number].append(index - last_seen[number])
            last_seen[number] = index

    result: dict[int, GapSummary] = {}
    for number, series in per_number.items():
        if not series:
            result[number] = GapSummary(count=0, min_gap=None, max_gap=None, avg_gap=None)
        else:
            result[number] = GapSummary(
                count=len(series),
                min_gap=min(series),
                max_gap=max(series),
                avg_gap=Decimal(sum(series)) / Decimal(len(series)),
            )
    # A number seen exactly once has no observed gap; emit an explicit zero
    # summary (never synthesized stats) for API/DB consumers (design D4).
    for number in last_seen:
        result.setdefault(number, GapSummary(count=0, min_gap=None, max_gap=None, avg_gap=None))
    return result


def null_aware_average(values: Iterable[Decimal | int | None]) -> Decimal | None:
    """Mean over NON-NULL draws only (design D4/STE-07); never imputes.

    Returns ``None`` when there is no non-NULL value. Arithmetic is `Decimal`
    exact on the raw values.
    """
    non_null = [value for value in values if value is not None]
    if not non_null:
        return None
    return sum((Decimal(v) for v in non_null), Decimal(0)) / Decimal(len(non_null))


def entropy_base2(counts: dict[int, int], min_number: int, max_number: int) -> Decimal:
    """Shannon entropy in bits over the rule-bounded universe (design §10).

    ``H = -Sigma_i p_i * log2(p_i)`` with ``p_i = count(i) / total``, iterating
    ``number`` ASC over ``[min_number, max_number]`` so zero-appearance numbers
    contribute ``0`` and every run over the same counts is identical. All
    arithmetic stays in `Decimal`; log2 is computed as ``ln(p)/ln(2)``.
    """
    total = sum(counts.values())
    if total == 0:
        return Decimal(0)
    entropy = Decimal(0)
    for number in range(min_number, max_number + 1):
        count = counts.get(number, 0)
        if count == 0:
            continue
        probability = Decimal(count) / Decimal(total)
        entropy -= probability * (probability.ln() / _LOG2_DENOMINATOR)
    return entropy.quantize(_ENTROPY_PRECISION)
