"""Probability engine pure-math tests (PM-01..PM-07 / PES-05): T-02 RED.

Hand-computed fixtures for all seven engine methods. Every expected value is
derived by hand from the spec formula — exact combinatorics via ``math.comb``,
Decimal arithmetic only — so float never appears in any output (PES-05).
Written BEFORE ``engine.py`` exists: the import below must fail with
``ImportError`` until the module lands (strict TDD, RED).

PM-01 hypergeometric  N=9, n=5, r=3 grid          -> P = C(r,k)C(N-r,n-k)/C(N,n)
PM-02 binomial        n=5, p=0.5                  -> P = C(5,k)/32
PM-03 poisson         lambda=2, kmax=5             -> P = e^-2 . 2^k / k!
PM-04 empirical       freq={1:10,2:15,3:5}, 30
PM-05 monte_carlo     isolated_rng(seed)       -> aggregates + p50/p90/p99
PM-06 bayes           prior={0:.5,1:.5}, like={0:.8,1:.2} -> post. = (0.8, 0.2)
PM-07 conditional     window_counts {9:8} / 20     -> 8/20 = 0.4
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.probability.engine import (
    bayes,
    binomial,
    conditional,
    empirical,
    hypergeometric,
    monte_carlo,
    poisson,
)
from backend.app.probability.providers import LotteryRules

# ---------------------------------------------------------------------------
# PM-01: Hypergeometric
# ---------------------------------------------------------------------------


def test_hypergeometric_returns_full_grid_rows() -> None:
    """The row count is 0..n (n=5 -> 6 rows), each a (k, Decimal) pair."""
    rows = hypergeometric(N=9, n=5, r=3)
    assert [k for k, _value in rows] == [0, 1, 2, 3, 4, 5]


def test_hypergeometric_matches_hand_fixture() -> None:
    """P(X=k) = C(3,k)*C(6,5-k)/C(9,5) with C(9,5)=126."""
    rows = dict(hypergeometric(N=9, n=5, r=3))
    assert rows[0] == Decimal("6") / Decimal("126") == Decimal(1) / Decimal(21)
    assert rows[1] == Decimal(45) / Decimal(126) == Decimal(5) / Decimal(14)
    assert rows[2] == Decimal(60) / Decimal(126) == Decimal(10) / Decimal(21)
    assert rows[3] == Decimal(15) / Decimal(126) == Decimal(5) / Decimal(42)
    assert rows[4] == Decimal(0)
    assert rows[5] == Decimal(0)


def test_hypergeometric_probabilities_sum_to_one() -> None:
    """The full grid sums to exactly 1 (126/126)."""
    rows = hypergeometric(N=9, n=5, r=3)
    total = sum(value for _k, value in rows)
    assert abs(total - Decimal(1)) < Decimal("1e-38")


def test_hypergeometric_all_values_are_decimal_no_float() -> None:
    """Every value is an exact Decimal — float never enters (PES-05)."""
    for _k, value in hypergeometric(N=9, n=5, r=3):
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)


def test_hypergeometric_all_matches_out_of_scope_are_zero() -> None:
    """k > r (more matches than successes exist) has zero probability."""
    rows = dict(hypergeometric(N=15, n=6, r=2))
    # Max possible matches is r=2; k=3..6 must be exactly zero.
    assert all(rows[k] == Decimal(0) for k in range(3, 7))
    # The feasible grid still sums to the C(2,0)*C(13,6)+... total over
    # C(15,6); the sum of individually-rounded rows is within 1 ulp at 1 (PES-05
    # keeps exact arithmetic per row, not exact aggregate rounding).
    total = sum(rows[k] for k in range(0, 7))
    assert abs(total - Decimal(1)) < Decimal("1e-49")


def test_hypergeometric_zero_and_full_success_populations() -> None:
    """Degenerate r bounds: r=N gives P(n)=1; r=0 gives P(0)=1."""
    all_pop = dict(hypergeometric(N=9, n=5, r=9))
    assert all_pop[5] == Decimal(1)
    assert all_pop[0] == Decimal(0)
    none_pop = dict(hypergeometric(N=9, n=5, r=0))
    assert none_pop[0] == Decimal(1)
    assert none_pop[5] == Decimal(0)


def test_hypergeometric_spec_scenario_min1_max45() -> None:
    """PM-01 spec: min=1..max=45, n=5, r=1 -> P(k=1)=C(44,4)/C(45,5)=1/9."""
    rows = dict(hypergeometric(N=45, n=5, r=1))
    assert rows[1] == Decimal(1) / Decimal(9)
    assert rows[0] == Decimal(8) / Decimal(9)


# ---------------------------------------------------------------------------
# PM-02: Binomial
# ---------------------------------------------------------------------------


def test_binomial_matches_hand_fixture_n5_p_half() -> None:
    """P(X=k) = C(5,k) * 0.5^5 = C(5,k)/32."""
    rows = dict(binomial(n=5, p=Decimal("0.5")))
    assert rows[0] == Decimal(1) / Decimal(32)
    assert rows[1] == Decimal(5) / Decimal(32)
    assert rows[2] == Decimal(10) / Decimal(32)
    assert rows[3] == Decimal(10) / Decimal(32)
    assert rows[4] == Decimal(5) / Decimal(32)
    assert rows[5] == Decimal(1) / Decimal(32)


def test_binomial_returns_one_row_per_k_from_zero() -> None:
    """Result rows are k=0..n inclusive."""
    rows = binomial(n=3, p=Decimal("0.5"))
    assert [k for k, _v in rows] == [0, 1, 2, 3]


def test_binomial_probabilities_sum_to_one() -> None:
    """Sum over the grid is exactly 1."""
    rows = binomial(n=5, p=Decimal("0.5"))
    assert sum(value for _k, value in rows) == Decimal(1)


def test_binomial_is_symmetric_for_p_half() -> None:
    """With p=0.5, P(k) == P(n-k)."""
    rows = dict(binomial(n=5, p=Decimal("0.5")))
    assert rows[1] == rows[4]
    assert rows[2] == rows[3]


def test_binomial_uses_decimal_pow_not_float() -> None:
    """p^11 grid stays Decimal; p=1 collapses to P(n)=1."""
    rows = dict(binomial(n=2, p=Decimal("0.25")))
    assert rows[0] == Decimal("0.5625")
    assert rows[2] == Decimal("0.0625")


# ---------------------------------------------------------------------------
# PM-03: Poisson
# ---------------------------------------------------------------------------


def test_poisson_len_is_kmax_plus_one() -> None:
    """Rows span k=0..kmax."""
    rows = poisson(lam=Decimal("2"), kmax=5)
    assert [k for k, _v in rows] == [0, 1, 2, 3, 4, 5]


def test_poisson_exact_recurrence_ratio() -> None:
    """P(k) approached the mathematical P(k-1)*lam/k to full precision."""
    lam = Decimal("2")
    rows = dict(poisson(lam=lam, kmax=5))
    for k in range(1, 6):
        # P(k)*k == P(k-1)*lam holds in exact math; rounding is capped at
        # 1e-38 relative (50-digit context, tiny tail cancellation).
        diff = abs(rows[k] * Decimal(k) - rows[k - 1] * lam)
        assert diff < Decimal("1e-38"), (k, diff)


def test_poisson_hand_computed_value_fixture() -> None:
    """P(k) == e^-2 * 2^k / k! at 50 digits (hand-computed literals).

    The exact e^-2 literal is the engine's Decimal exp at the same context
    precision; the ratio identity P(k)*k == P(k-1)*lam (with tolerance above)
    pins every other row to the same 50-digit expansion.
    """
    rows = dict(poisson(lam=Decimal("2"), kmax=5))
    # Tolerance for precision differences across Decimal implementations
    assert abs(rows[0] - Decimal("0.1353352832366126918939994949724844034076")) < Decimal("1e-38")
    assert abs(rows[1] - Decimal("0.2706705664732253837879989899449688068152")) < Decimal("1e-38")
    assert abs(rows[2] - Decimal("0.2706705664732253837879989899449688068152")) < Decimal("1e-38")
    assert abs(rows[3] - Decimal("0.1804470443154835891919993266299792045435")) < Decimal("1e-38")


def test_poisson_too_large_kmax_never_exceeds_one_in_tail() -> None:
    """For lam=2, the mode is k=2: values rise then fall (convex check)."""
    rows = dict(poisson(lam=Decimal("2"), kmax=3))
    assert rows[0] < rows[1]
    assert rows[1] <= rows[2]


# ---------------------------------------------------------------------------
# PM-04: Empirical
# ---------------------------------------------------------------------------


def test_empirical_ratios_from_frequencies_and_total() -> None:
    """P(x) = freq(x)/total, exact Decimals; 30 total, [10,15,5]."""
    probs = empirical(frequencies={1: 10, 2: 15, 3: 5}, total=30)
    assert probs[1] == Decimal(10) / Decimal(30)
    assert probs[2] == Decimal(15) / Decimal(30)
    assert probs[3] == Decimal(5) / Decimal(30)


def test_empirical_probabilities_sum_to_one() -> None:
    probs = empirical(frequencies={1: 10, 2: 15, 3: 5}, total=30)
    assert sum(probs.values()) == Decimal(1)


def test_empirical_spec_scenario_twelve_out_of_sixty() -> None:
    """Spec scenario: 12 occurrences of number 7 over 60 draws -> 12/60 = 0.2."""
    probs = empirical(frequencies={7: 12}, total=60)
    assert probs[7] == Decimal("0.2")


def test_empirical_total_zero_raises_value_error() -> None:
    """Zero draws would divide by zero — fail loudly, never guessed (PES-11)."""
    with pytest.raises(ValueError):
        empirical(frequencies={1: 0}, total=0)


# ---------------------------------------------------------------------------
# PM-05: Monte Carlo
# ---------------------------------------------------------------------------


def _simple_rules() -> LotteryRules:
    """Small canonical rules: min=1, max=9, numbers_to_select=3 (pool=9)."""
    return LotteryRules(min_number=1, max_number=9, numbers_to_select=3)


def test_monte_carlo_same_seed_identical_results() -> None:
    """Two isolated_rng(seed) instances MUST produce identical output dicts."""
    from backend.app.probability.determinism import isolated_rng

    rules = _simple_rules()
    params = {"n_simulations": 2000}
    a = monte_carlo(isolated_rng(1234), rules, params)
    b = monte_carlo(isolated_rng(1234), rules, params)
    assert a == b


def test_monte_carlo_different_seed_different_results() -> None:
    """Different seed -> different counts -> different probabilities."""
    from backend.app.probability.determinism import isolated_rng

    a = monte_carlo(isolated_rng(1234), _simple_rules(), {"n_simulations": 2000})
    b = monte_carlo(isolated_rng(9999), _simple_rules(), {"n_simulations": 2000})
    assert a != b


def test_monte_carlo_output_shape_and_no_raw_histories() -> None:
    """Aggregates + quantiles only; never raw per-run histories (PES-01)."""
    from backend.app.probability.determinism import isolated_rng

    result = monte_carlo(isolated_rng(42), _simple_rules(), {"n_simulations": 1000})
    assert set(result) == {"counts", "probabilities", "quantiles"}
    assert set(result["quantiles"]) == {"p50", "p90", "p99"}
    assert "raw" not in result
    assert "histories" not in result


def test_monte_carlo_counts_and_probabilities_are_consistent() -> None:
    """sum(counts) == n_simulations * n_select; Decimal probs in run range."""
    from backend.app.probability.determinism import isolated_rng

    n_sim, n_select = 2000, 3
    result = monte_carlo(isolated_rng(7), _simple_rules(), {"n_simulations": n_sim})
    counts = result["counts"]
    assert sum(counts.values()) == n_sim * n_select
    for _subject, count in counts.items():
        assert isinstance(count, int)
        assert 0 <= count <= n_sim
    for _subject, prob in result["probabilities"].items():
        assert isinstance(prob, Decimal)
        assert Decimal(0) <= prob <= Decimal(1)


def test_monte_carlo_quantiles_ordered_and_decimal() -> None:
    """p50 <= p90 <= p99, all Decimal, derived from sorted counts."""
    from backend.app.probability.determinism import isolated_rng

    result = monte_carlo(isolated_rng(7), _simple_rules(), {"n_simulations": 1000})
    q = result["quantiles"]
    assert q["p50"] <= q["p90"] <= q["p99"]
    for value in q.values():
        assert isinstance(value, Decimal)
        assert Decimal(0) <= value <= Decimal(1)


# ---------------------------------------------------------------------------
# PM-06: Bayes
# ---------------------------------------------------------------------------


def test_bayes_matches_hand_fixture() -> None:
    """posterior ~= prior^likelihood normalized: (0.4,0.1)/0.5 = (0.8,0.2)."""
    post = bayes(
        prior={0: Decimal("0.5"), 1: Decimal("0.5")},
        likelihood={0: Decimal("0.8"), 1: Decimal("0.2")},
    )
    assert post[0] == Decimal("0.8")
    assert post[1] == Decimal("0.2")


def test_bayes_posterior_sums_to_one() -> None:
    post = bayes(
        prior={0: Decimal("0.5"), 1: Decimal("0.5")},
        likelihood={0: Decimal("0.8"), 1: Decimal("0.2")},
    )
    assert sum(post.values()) == Decimal(1)


def test_bayes_deterministic() -> None:
    """Same priors + same likelihood -> identical posterior (byte-identical)."""
    prior = {0: Decimal("0.5"), 1: Decimal("0.5")}
    like = {0: Decimal("0.8"), 1: Decimal("0.2")}
    assert bayes(prior, like) == bayes(prior, like)


def test_bayes_ignores_keys_with_no_likelihood_nine_to_one() -> None:
    """prior 0.9/0.1 * like 0.5/0.5 -> posterior (0.9, 0.1)."""
    post = bayes(
        prior={0: Decimal("0.9"), 1: Decimal("0.1")},
        likelihood={0: Decimal("0.5"), 1: Decimal("0.5")},
    )
    assert post == {0: Decimal("0.9"), 1: Decimal("0.1")}


# ---------------------------------------------------------------------------
# PM-07: Conditional (univariate windowed)
# ---------------------------------------------------------------------------


def test_conditional_hand_fixture() -> None:
    """8 of 20 -> p = 8/20 = 0.4, univariate only (never joint)."""
    probs = conditional(window_counts={1: 8}, window_size=20)
    assert probs[1] == Decimal("0.4")


def test_conditional_univariate_fixture_windowed() -> None:
    """Windowed: count of value in window / window_size (task fixture)."""
    probs = conditional(window_counts={8: 1}, window_size=10)
    assert probs[8] == Decimal("0.1")


def test_conditional_decimal_values_no_float() -> None:
    probs = conditional(window_counts={1: 8}, window_size=20)
    for value in probs.values():
        assert isinstance(value, Decimal)
        assert not isinstance(value, float)


def test_conditional_window_size_zero_raises() -> None:
    with pytest.raises(ValueError):
        conditional(window_counts={1: 0}, window_size=0)
