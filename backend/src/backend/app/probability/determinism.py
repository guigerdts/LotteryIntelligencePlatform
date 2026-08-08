"""Determinism seed policy for Monte Carlo (PES-05 / design D2).

The Monte Carlo model MUST run from an isolated ``random.Random(seed)`` — never
the global ``random`` module and never OS entropy. The seed is derived from a
canonical SHA-256 over ``{input_fingerprint, model_params, n_simulations,
PROB_GENERATOR_VERSION}`` so the same versioned inputs always produce the same
seed (byte-identical rerun), and any parameter change produces a NEW deterministic
run while the old snapshot keeps its seed/values (PES-04/PES-05).
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping

from backend.app.probability import PROB_GENERATOR_VERSION
from backend.app.probability.fingerprint import _canonical_json


def derive_seed(
    input_fingerprint: str,
    model_params: Mapping[str, object] | None = None,
    n_simulations: int = 1_000,
) -> int:
    """Return the deterministic Monte Carlo seed for a versioned run.

    ``seed = int.from_bytes(sha256(canonical_json({input_fingerprint,
    model_params, n_simulations, PROB_GENERATOR_VERSION})).digest()[:16], "big")``.
    ``n_simulations`` participates in the seed (PES-05): changing it changes the
    run deterministically; the same inputs always reproduce the same seed.
    """
    payload = {
        "input_fingerprint": input_fingerprint,
        "model_params": dict(model_params) if model_params is not None else {},
        "n_simulations": n_simulations,
        "PROB_GENERATOR_VERSION": PROB_GENERATOR_VERSION,
    }
    canonical = _canonical_json(payload).encode("utf-8")
    return int.from_bytes(hashlib.sha256(canonical).digest()[:16], "big")


def isolated_rng(seed: int) -> random.Random:
    """Return an isolated ``random.Random(seed)`` for one Monte Carlo run.

    The engine MUST use this instance (or one derived from it) and NEVER the
    global ``random`` module — global state would break byte-identical reruns.
    """
    return random.Random(seed)


__all__ = ["derive_seed", "isolated_rng"]