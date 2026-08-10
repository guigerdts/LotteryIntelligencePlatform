"""Canonical input fingerprint for optimization snapshots (OE-07).

SHA-256 over ``sort_keys=True`` canonical JSON of
``{optimizer, algorithm_params, objective_metric, objective_direction,
search_space, data_hash, seed, version, termination_params}``: key order at
any nesting level is irrelevant, so equal inputs yield byte-identical hex.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def compute_opt_fingerprint(
    optimizer: str,
    algorithm_params: Mapping[str, object],
    objective_metric: str,
    objective_direction: str,
    search_space: Mapping[str, object],
    data_hash: str,
    seed: int,
    version: str,
    termination_params: Mapping[str, object] | None = None,
) -> str:
    """Return the canonical SHA-256 hex fingerprint for one optimization run.

    All inputs are copied before serialization so caller-side mutation can
    never change the digest after the fact.
    """
    payload = {
        "optimizer": optimizer,
        "algorithm_params": dict(algorithm_params),
        "objective_metric": objective_metric,
        "objective_direction": objective_direction,
        "search_space": dict(search_space),
        "data_hash": data_hash,
        "seed": seed,
        "version": version,
        "termination_params": dict(termination_params) if termination_params else None,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["compute_opt_fingerprint"]
