"""Canonical input fingerprint for the Feature Engine (FES-05, design §5).

The digest is SHA-256 over canonical compact JSON (``sort_keys=True`` +
``separators=(",", ":")``) of the *inputs* — draws identity, ordered feature identity
list, and optional stats identity — NOT the outputs. It is the invalidation key: a new
snapshot compares it against the stored one to decide recompute. Float never enters this
path; ``Decimal``/tuples/`Mapping` are normalized to a stable, jsonable form first.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any


def _jsonable(value: Any) -> Any:
    """Map a feature-input ``value`` to a json.dumps-stable, order-independent primitive.

    ``Decimal`` becomes its canonical string (deterministic, no float representation);
    mappings are recursed and key-ordered by ``json.dumps(sort_keys=True)``; sequences
    are converted to lists and sorted recursively so list order never changes the digest
    (FES-05 canonical form — the spec sorts ``features`` before fingerprinting).
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


def feature_input_fingerprint(payload: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 hex digest of an input ``payload``.

    ``payload`` is ``{draws: {...}, features: [...], stats: {...} | None}`` (design §4).
    Any insertion order, feature scramble, or dict construction yields the same digest
    because ``sort_keys=True`` orders every level and compact separators avoid
    whitespace ambiguity (FES-05). Stats is optional; omitting it changes the digest.
    """
    canonical = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def draw_set_fingerprint(
    *,
    lottery: int,
    from_draw: int,
    to_draw: int,
    draw_rows_checksum: str,
) -> str:
    """Fingerprint of the draw-set identity used inside the input fingerprint.

    Purely documentary helper matching design §5's ``draws: {lottery, from, to,
    checksum}`` block; the checksum itself is computed by the provider from the ordered
    draw rows (``ORDER BY draw_number, id``).
    """
    return feature_input_fingerprint(
        {
            "draws": {
                "lottery": lottery,
                "from": from_draw,
                "to": to_draw,
                "checksum": draw_rows_checksum,
            }
        }
    )
