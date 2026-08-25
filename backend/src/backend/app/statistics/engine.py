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

import math
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


@dataclass(frozen=True)
class BiasReport:
    """Fairness diagnostic over draw history (STE-14)."""

    status: str  # "fair" | "anomalous"
    chi_square: Decimal
    p_value: float
    runs_z: float
    outliers: list[int]


def _gser(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) via series (Numerical Recipes)."""
    if x <= 0.0:
        return 0.0
    gln = math.lgamma(a)
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(200):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-12:
            break
    return total * math.exp(-x + a * math.log(x) - gln)


def _gcf(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) via continued fraction."""
    fpmax = 1e-300
    gln = math.lgamma(a)
    b = x + 1.0 - a
    c = 1.0 / fpmax
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmax:
            d = fpmax
        c = b + an / c
        if abs(c) < fpmax:
            c = fpmax
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def _gammq(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) = 1 - P(a, x)."""
    if x < 0.0 or a <= 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


def chi_square_gof(
    counts: dict[int, int], min_number: int, max_number: int
) -> tuple[Decimal, float]:
    """Chi-square goodness-of-fit of observed frequencies vs uniform (STE-14).

    Returns (chi_square statistic, p_value). ``p_value`` is the upper-tail
    probability under ``df = (max-min)`` degrees of freedom. Uses float only for
    the diagnostic p-value (never enters a snapshot checksum).
    """
    total = sum(counts.values())
    n = max_number - min_number + 1
    if total == 0:
        return Decimal(0), 1.0
    expected = Decimal(total) / Decimal(n)
    chi2 = Decimal(0)
    for number in range(min_number, max_number + 1):
        observed = Decimal(counts.get(number, 0))
        diff = observed - expected
        chi2 += (diff * diff) / expected
    chi2 = chi2.quantize(Decimal("0.0001"))
    df = float(n - 1)
    p_value = _gammq(df / 2.0, float(chi2) / 2.0)
    return chi2, p_value


def runs_test(
    numbers: Iterable[Iterable[int]], min_number: int, max_number: int
) -> float:
    """Wald-Wolfowitz runs test z-score for sequential independence (STE-14).

    A draw is a SET, not an ordered sequence, so the test is applied to the
    time-ordered series of per-draw sums (one scalar per draw). Each sum is
    labeled above/below the series median; ``|z|`` far from 0 suggests the draw
    outcomes are not independent over time.
    """
    sums = [sum(draw) for draw in numbers]
    if len(sums) < 2:
        return 0.0
    median = sum(sums) / len(sums)
    labels = [1 if s >= median else 0 for s in sums]
    n1 = sum(labels)
    n2 = len(sums) - n1
    if n1 == 0 or n2 == 0:
        return 0.0
    runs = 1
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            runs += 1
    expected = 1.0 + 2.0 * n1 * n2 / (n1 + n2)
    variance = (
        2.0
        * n1
        * n2
        * (2.0 * n1 * n2 - n1 - n2)
        / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    )
    if variance <= 0.0:
        return 0.0
    return (runs - expected) / variance**0.5


def bias_report(
    counts: dict[int, int],
    numbers: Iterable[Iterable[int]],
    min_number: int,
    max_number: int,
) -> BiasReport:
    """Assemble a `BiasReport` from frequencies + raw draws (STE-14).

    Flags ``anomalous`` when the chi-square p-value is below 0.01, the runs
    |z| exceeds 3, or any number's observed frequency deviates beyond
    ``4 * sqrt(expected)`` (those numbers are listed as outliers).
    """
    chi2, p_value = chi_square_gof(counts, min_number, max_number)
    runs_z = runs_test(numbers, min_number, max_number)

    total = sum(counts.values())
    n = max_number - min_number + 1
    expected = total / n if n else 0.0
    threshold = 4.0 * (expected**0.5) if expected > 0 else 0.0
    outliers: list[int] = []
    for number in range(min_number, max_number + 1):
        deviation = abs(counts.get(number, 0) - expected)
        if threshold > 0 and deviation > threshold:
            outliers.append(number)

    anomalous = (p_value < 0.01) or (abs(runs_z) > 3.0) or bool(outliers)
    return BiasReport(
        status="anomalous" if anomalous else "fair",
        chi_square=chi2,
        p_value=p_value,
        runs_z=runs_z,
        outliers=outliers,
    )
