"""Determinism / seed policy tests (PES-05 / D2): T-06.

The Monte Carlo seed MUST be derived deterministically from the canonical SHA-256
of ``{input_fingerprint, model_params, n_simulations, PROB_GENERATOR_VERSION}``
and MUST use an isolated ``random.Random(seed)`` — never the global ``random``
module. Changing ``n_simulations`` MUST produce a different seed while remaining
deterministic.
"""

from __future__ import annotations

import random

from backend.app.probability.determinism import derive_seed, isolated_rng
from backend.app.probability.registry import PROB_GENERATOR_VERSION


def test_seed_is_deterministic_for_identical_inputs() -> None:
    """Same fingerprint + params + n_simulations + version -> same seed."""
    first = derive_seed(
        input_fingerprint="fp-1", model_params={"p": "0.5"}, n_simulations=1000
    )
    second = derive_seed(
        input_fingerprint="fp-1", model_params={"p": "0.5"}, n_simulations=1000
    )
    assert first == second
    assert first >= 0


def test_seed_changes_when_n_simulations_changes() -> None:
    """A different ``n_simulations`` MUST produce a different seed (PES-05)."""
    a = derive_seed(input_fingerprint="fp-1", model_params={}, n_simulations=1000)
    b = derive_seed(input_fingerprint="fp-1", model_params={}, n_simulations=2000)
    assert a != b


def test_seed_changes_when_fingerprint_or_params_change() -> None:
    """Different fingerprint or params -> different seed."""
    a = derive_seed(input_fingerprint="fp-a", model_params={"p": "0.5"}, n_simulations=100)
    b = derive_seed(input_fingerprint="fp-a", model_params={"p": "0.6"}, n_simulations=100)
    c = derive_seed(input_fingerprint="fp-b", model_params={"p": "0.5"}, n_simulations=100)
    assert a != b
    assert a != c


def test_seed_formula_matches_design() -> None:
    """The seed equals the design formula (PES-05): sha256 canonical JSON, first 16 bytes."""
    import hashlib
    import json

    canonical = json.dumps(
        {
            "input_fingerprint": "fp-1",
            "model_params": {"p": "0.5"},
            "n_simulations": 1000,
            "PROB_GENERATOR_VERSION": PROB_GENERATOR_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected = int.from_bytes(hashlib.sha256(canonical).digest()[:16], "big")
    assert derive_seed("fp-1", {"p": "0.5"}, 1000) == expected


def test_isolated_rng_is_random_random_instance() -> None:
    """``isolated_rng`` returns an isolated ``random.Random``, never the global module."""
    rng = isolated_rng(42)
    assert isinstance(rng, random.Random)
    assert rng is not random  # the module object itself is never returned


def test_isolated_rng_is_deterministic_rerun() -> None:
    """Same seed -> same sequence; different seed -> different sequence."""
    first = isolated_rng(1234)
    second = isolated_rng(1234)
    third = isolated_rng(5678)
    assert [first.random() for _ in range(5)] == [second.random() for _ in range(5)]
    assert [first.random() for _ in range(5)] != [third.random() for _ in range(5)]