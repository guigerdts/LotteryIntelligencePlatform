"""Generator identity helpers — deterministic seed and snapshot fingerprint.

Pure utilities for GEN-008 (snapshot fingerprint) and GEN-009 (run seed).
They reuse the F5 primitives ``derive_seed`` (``probability.determinism``) and
``_canonical_json`` (``probability.fingerprint``) — the GEN-015 reuse surface —
instead of inlining the hashing logic into the service. This mirrors the repo
precedent: probability delegates identity to ``probability/determinism.py`` +
``probability/fingerprint.py``, meta delegates to ``meta/ranking.py``.

Boundaries: no DB access, no engine imports, no F11/F12 reads (GEN-016).
"""

from __future__ import annotations

import hashlib

from backend.app.probability.determinism import derive_seed
from backend.app.probability.fingerprint import _canonical_json


def generation_seed(
    selection_fingerprint: str,
    lottery_id: int,
    count: int,
    version: str,
) -> int:
    """Return the deterministic run seed for one generation (GEN-009).

    ``seed = derive_seed(input_fingerprint, model_params={"lottery_id": L,
    "count": C}, n_simulations=C)`` where ``input_fingerprint =
    SHA-256(_canonical_json({selection_fingerprint, lottery_id, count,
    GENERATOR_VERSION}))`` (design §Determinism). Same versioned inputs always
    produce the same seed; any input change produces a NEW seed deterministically.
    """
    input_fingerprint = hashlib.sha256(
        _canonical_json(
            {
                "selection_fingerprint": selection_fingerprint,
                "lottery_id": lottery_id,
                "count": count,
                "GENERATOR_VERSION": version,
            }
        ).encode("utf-8")
    ).hexdigest()
    return derive_seed(
        input_fingerprint,
        model_params={"lottery_id": lottery_id, "count": count},
        n_simulations=count,
    )


def snapshot_fingerprint(
    lottery_id: int,
    selection_id: int,
    count: int,
    seed: int,
    version: str,
) -> str:
    """Return the canonical SHA-256 snapshot identity (GEN-008).

    Digest covers ``{lottery_id, selection_id, count, seed, VERSION}`` so any
    input change produces a new snapshot identity, making idempotency exact:
    same fingerprint → existing snapshot, no new rows (GEN-008).
    """
    payload = _canonical_json(
        {
            "lottery_id": lottery_id,
            "selection_id": selection_id,
            "count": count,
            "seed": seed,
            "VERSION": version,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["generation_seed", "snapshot_fingerprint"]
