"""Determinism contract for the ML engine (MLE-05 / D2 / D4).

Every metric is quantized to a ``Decimal`` with 8 fraction digits — the canonical
``Numeric(20,8)`` form — BEFORE any checksum digest or persistence: a raw float
never feeds a fingerprint, checksum, or stored row. ``get_deterministic_state``
seeds the numpy RNG so every family consumes the same random stream across
reruns (same-environment determinism, D2).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Final

import numpy as np

QUANTIZE_PRECISION: Final[int] = 8
# Decimal("0.00000001") — the rounding quantum for Numeric(20,8).
_QUANTUM = Decimal((0, (1,), -QUANTIZE_PRECISION))


def get_deterministic_state(seed: int = 0) -> np.random.RandomState:
    """Return a seeded RNG so every model family trains on the same stream (D2)."""
    return np.random.RandomState(seed)


def quantize_metric(value: Real) -> Decimal:
    """Round ``value`` to a ``Decimal`` with 8 fraction digits (Numeric(20,8)).

    Quantizes via ``str`` (exact round-trip, no binary-float artifacts), matching
    design M-A7 ``Decimal(str(x)).quantize("0.00000001")``.
    """
    return Decimal(str(value)).quantize(_QUANTUM)


def compute_metrics_checksum(metrics: Mapping[str, Real]) -> str:
    """SHA-256 over canonical JSON of the Decimal-QUANTIZED metric payload.

    Quantization happens before serialization: the digest depends only on the
    quantized values, so two raw floats that quantize identically yield the same
    checksum and raw floats never feed the digest (MLE-05 scenario "float
    excluded from checksum").
    """
    quantized = {name: str(quantize_metric(value)) for name, value in metrics.items()}
    canonical = json.dumps(quantized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "QUANTIZE_PRECISION",
    "get_deterministic_state",
    "quantize_metric",
    "compute_metrics_checksum",
]
