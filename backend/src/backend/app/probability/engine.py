"""Pure probability computation engine (PES-05/06, PM-01..07).

No DB, no concrete imports. All Integer/Decimal; exact combinatorics via
``math.comb``. Float never enters an output value (PES-05). Every function is
deterministic: identical inputs yield byte-identical results, and the Monte
Carlo model consumes only the isolated ``random.Random(seed)`` it receives —
never the global ``random`` module (PES-05 seed policy).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal, getcontext
from typing import Any

from backend.app.probability.providers import LotteryRules

# High-precision Decimal context so division/exp never truncates early (PES-05).
getcontext().prec = 50


def hypergeometric(N: int, n: int, r: int) -> list[tuple[int, Decimal]]:
    """PM-01: Hypergeometric distribution over the lottery pool.

    P(X=k) = C(r,k) * C(N-r, n-k) / C(N, n)
    N = population size (max - min + 1), n = draws, r = success states in the
    population. Returns one (k, Decimal) row per k in 0..n; k > r or
    n-k > N-r yields exactly zero (C(a, b) = 0 for b > a).
    """
    if N < 1 or n < 0 or r < 0:
        raise ValueError(f"invalid hypergeometric inputs N={N}, n={n}, r={r}")
    if n > N or r > N:
        raise ValueError(f"n={n} and r={r} must not exceed population N={N}")
    total = math.comb(N, n)
    rows: list[tuple[int, Decimal]] = []
    for k in range(n + 1):
        exact = math.comb(r, k) * math.comb(N - r, n - k)
        rows.append((k, Decimal(exact) / Decimal(total)))
    return rows


def binomial(n: int, p: Decimal) -> list[tuple[int, Decimal]]:
    """PM-02: Binomial distribution with declared ``p`` and ``n``.

    P(X=k) = C(n,k) * p^k * (1-p)^(n-k), exact Decimal for k in 0..n.
    """
    if n < 0:
        raise ValueError(f"invalid binomial trials n={n}")
    if not (Decimal(0) <= p <= Decimal(1)):
        raise ValueError(f"p must be in [0, 1], got {p}")
    rows: list[tuple[int, Decimal]] = []
    for k in range(n + 1):
        exact = math.comb(n, k) * p**k * (Decimal(1) - p) ** (n - k)
        rows.append((k, Decimal(exact)))
    return rows


def poisson(lam: Decimal, kmax: int) -> list[tuple[int, Decimal]]:
    """PM-03: Poisson distribution at fixed Decimal precision.

    P(X=k) = e^(-lam) * lam^k / k! for k in 0..kmax. Uses Decimal exp so the
    whole row is exact to the module context precision (PES-05: float rejected).
    """
    if lam < 0:
        raise ValueError(f"lam must be >= 0, got {lam}")
    if kmax < 0:
        raise ValueError(f"kmax must be >= 0, got {kmax}")
    exp_neg = (-lam).exp()
    rows: list[tuple[int, Decimal]] = []
    for k in range(kmax + 1):
        rows.append((k, exp_neg * lam**k / Decimal(math.factorial(k))))
    return rows


def empirical(frequencies: Mapping[int, int], total: int) -> dict[int, Decimal]:
    """PM-04: Empirical probability from stored frequency counts.

    P(x) = frequency(x) / total, where ``total`` is the snapshot draw count.
    A non-positive ``total`` raises ``ValueError`` — zero draws are never
    guessed (PES-11); the caller maps that to an empty-header state instead.
    """
    if total <= 0:
        raise ValueError(f"total must be positive, got {total}")
    total_dec = Decimal(total)
    return {subject: Decimal(count) / total_dec for subject, count in frequencies.items()}


def monte_carlo(rng: Any, rules: LotteryRules, params: Mapping[str, Any]) -> dict[str, Any]:
    """PM-05: Fixed-seed Monte Carlo simulation over lottery rules.

    Draws ``n_simulations`` random selections of ``numbers_to_select`` numbers
    from the pool using the ISOLATED ``rng`` instance only (never the global
    ``random`` module — PES-05). Accumulates integer per-subject counts, then
    returns per-subject probabilities ``Decimal(count)/n`` plus p50/p90/p99
    quantiles over the sorted probability aggregates. NEVER returns raw
    simulation histories (PES-01). ``params`` must declare ``n_simulations``.
    """
    n_simulations = int(params["n_simulations"])
    if n_simulations <= 0:
        raise ValueError(f"n_simulations must be positive, got {n_simulations}")
    pool = list(range(rules.min_number, rules.max_number + 1))
    n_select = rules.numbers_to_select
    if n_select < 1 or n_select > len(pool):
        raise ValueError(f"numbers_to_select={n_select} outside pool of {len(pool)}")

    counts = {number: 0 for number in pool}
    for _ in range(n_simulations):
        for number in rng.sample(pool, n_select):
            counts[number] += 1

    probabilities = {
        number: Decimal(count) / Decimal(n_simulations) for number, count in counts.items()
    }
    sorted_probs = sorted(probabilities.values())
    quantiles = {
        "p50": _percentile(sorted_probs, 50),
        "p90": _percentile(sorted_probs, 90),
        "p99": _percentile(sorted_probs, 99),
    }
    return {"counts": counts, "probabilities": probabilities, "quantiles": quantiles}


def _percentile(sorted_values: Sequence[Decimal], p: int) -> Decimal:
    """Nearest-rank percentile over an ascending ``Decimal`` sequence (PES-05).

    Pure integer index math — ``float`` never enters the value (index is
    ``ceil(p * n / 100) - 1``, clamped to the last element).
    """
    n = len(sorted_values)
    if n == 0:
        raise ValueError("cannot compute a percentile over an empty sequence")
    index = max(0, min(n - 1, math.ceil(p * n / 100) - 1))
    return sorted_values[index]


def bayes(prior: Mapping[Any, Any], likelihood: Mapping[Any, Any]) -> dict[Any, Decimal]:
    """PM-06: Empirical-Bayes posterior by pure normalized fold.

    posterior(A) proportional to prior(A) * likelihood(A), then normalized over
    the union of subjects; a subject absent from either map contributes zero
    (mathematically correct, never a guessed value — PES-06 parity). An all-zero
    product returns an empty dict (absent, never a bogus distribution).
    """
    raw: dict[Any, Decimal] = {}
    for subject in set(prior) | set(likelihood):
        p = Decimal(prior.get(subject, 0))
        like = Decimal(likelihood.get(subject, 0))
        raw[subject] = p * like
    total = sum(raw.values())
    if total == 0:
        return {}
    return {subject: value / total for subject, value in raw.items()}


def conditional(window_counts: Mapping[int, int], window_size: int) -> dict[int, Decimal]:
    """PM-07: Univariate conditional probability inside a declared window.

    P(x | window) = count(x in window) / window_size. UNIVARIATE ONLY — never
    joint/pairwise/co-occurrence (those stay out of scope until F6). A
    non-positive ``window_size`` raises ``ValueError`` (never guessed).
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be positive, got {window_size}")
    size = Decimal(window_size)
    return {subject: Decimal(count) / size for subject, count in window_counts.items()}


__all__ = [
    "bayes",
    "binomial",
    "conditional",
    "empirical",
    "hypergeometric",
    "monte_carlo",
    "poisson",
]
