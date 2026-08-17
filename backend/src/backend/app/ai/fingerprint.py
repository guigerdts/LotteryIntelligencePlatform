"""Canonical AI fingerprint (A-02): SHA-256 over sort_keys=True JSON of inputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def compute_ai_fingerprint(engine_version: str, function: str, inputs: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 hex digest of one engine invocation (A-02)."""
    payload = {"engine_version": engine_version, "function": function, "inputs": inputs}
    canonical = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()
