"""Canonical input fingerprint for the Probability Engine (PES-05, design §Seed).

The digest is SHA-256 over canonical compact JSON (``sort_keys=True`` +
``separators=(",", ":")``) of the *inputs* — draws identity, model identity list,
and optional stats identity — NOT the outputs. It is the invalidation key: a new
generation compares it against the stored one to decide recompute. Float never
enters this path; ``Decimal``/tuples/`Mapping` are normalized to a stable,
jsonable form first (mirrors ``feature_engineering.fingerprint``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any


def _jsonable(value: Any) -> Any:
    """Map a probability input value to a json.dumps-stable primitive.

    ``Decimal`` becomes its canonical string (deterministic, no float
    representation); mappings are recursed and key-ordered by
    ``json.dumps(sort_keys=True)``; sequences are converted to lists and sorted
    recursively so list order never changes the digest (PES-05 canonical form).
    ``None``/ints/bools/strs pass through.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [_jsonable(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialize ``payload`` with canonical, insertion-order-independent JSON."""
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))


def probability_input_fingerprint(payload: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 hex digest of a probability input ``payload``.

    Any insertion order or construction yields the same digest because
    ``sort_keys=True`` orders every level and compact separators avoid whitespace
    ambiguity (PES-05).
    """
    canonical = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()