"""SHA-256 fingerprint computation for experiment snapshots (EXP-002, NFR-EXP-02).

The fingerprint encodes experiment identity and content. Any change to
the inputs produces a different fingerprint, ensuring idempotent
re-creation detection.
"""

from __future__ import annotations

import hashlib
import json


def compute_exp_fingerprint(
    *,
    name: str,
    lottery_id: int,
    config_json: str | None,
    description: str | None,
    status: str,
) -> str:
    """Return a hex-encoded SHA-256 fingerprint for an experiment.

    Inputs mixed into the digest (EXP-002, NFR-EXP-02):
    - ``name`` — experiment identity.
    - ``lottery_id`` — lottery scope.
    - ``config_json`` — arbitrary engine configuration.
    - ``description`` — human-readable description.
    - ``status`` — lifecycle state.

    The payload is JSON-serialised with ``sort_keys=True`` so that
    identical logical inputs always yield the same digest.
    """
    payload = json.dumps(
        {
            "name": name,
            "lottery_id": lottery_id,
            "config_json": config_json,
            "description": description,
            "status": status,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
