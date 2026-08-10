"""Canonical input fingerprint for DL snapshots (DLE-08 / D-A4).

SHA-256 over ``sort_keys=True`` canonical JSON of
``{data_hash, hyperparameters, architecture, seed, window, cut, version}``:
key order at any nesting level is irrelevant, so equal inputs yield
byte-identical hex.  ``hyperparameters`` is nested per-model
(``{mlp: {...}, lstm: {...}}``) and MUST be JSON-serializable; ``window``
and ``cut`` participate in the digest, so a different walk-forward boundary
or sequence length always yields a new version.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def compute_dl_fingerprint(
    *,
    data_hash: str,
    hyperparameters: Mapping[str, object],
    architecture: str,
    seed: int,
    window: int,
    cut: int,
    version: str,
) -> str:
    """Return the canonical SHA-256 hex fingerprint for one DL training run.

    Every parameter is explicit (no *args) so callers cannot swap order.
    ``hyperparameters`` is copied before serialization so caller-side mutation
    can never change the digest after the fact.
    """
    payload = {
        "data_hash": data_hash,
        "hyperparameters": dict(hyperparameters),
        "architecture": architecture,
        "seed": seed,
        "window": window,
        "cut": cut,
        "version": version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["compute_dl_fingerprint"]
