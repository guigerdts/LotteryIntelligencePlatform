"""Canonical SHA-256 checksum for statistics snapshots (C2/STE-05, design §9).

The checksum is the determinism contract: same lottery content + same
``generator_version`` + same metric set MUST produce bit-identical digests
across databases. ``sort_keys=True`` + compact separators mirror
``import_service._dataset_checksum`` so the digest depends only on content,
never on insertion order or float representation — floats never enter this path
(design §9: INTEGER/Decimal accumulators only).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def stat_checksum(payload: Mapping[str, object]) -> str:
    """Return the canonical SHA-256 hex digest of a stats ``payload``.

    The ``payload`` is the fully-serialized snapshot content drawn from the pure
    engine metrics (frequencies, positions, gaps, averages, scalars) plus the
    version/range envelope. Any insertion order produces the same digest because
    ``json.dumps`` sorts keys at every level and uses compact separators.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
