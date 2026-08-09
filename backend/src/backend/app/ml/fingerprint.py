"""Canonical input fingerprint for ML snapshots (MLE-05 / D2 / design M-A5).

SHA-256 over ``sort_keys=True`` canonical JSON of
``{data_hash, params, generator_version, cut}``: key order at any nesting level
is irrelevant, so equal inputs yield byte-identical hex. ``params`` MUST be
JSON-serializable (hyperparameters only, never weights); ``cut`` participates in
the digest, so a different walk-forward boundary always yields a new version.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def compute_ml_fingerprint(
    data_hash: str,
    params: Mapping[str, object],
    generator_version: str,
    cut: int,
) -> str:
    """Return the canonical SHA-256 hex fingerprint for one training run.

    ``params`` is copied before serialization so caller-side mutation can never
    change the digest after the fact.
    """
    payload = {
        "data_hash": data_hash,
        "params": dict(params),
        "generator_version": generator_version,
        "cut": cut,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["compute_ml_fingerprint"]
