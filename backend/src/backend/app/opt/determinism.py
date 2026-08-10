"""Determinism contract for the Optimization Engine (OE-06/07).

Every metric is quantized to a ``Decimal`` with 8 fraction digits — the canonical
``Numeric(20,8)`` form — BEFORE any checksum digest or persistence: a raw float
never feeds a fingerprint, checksum, or stored row. This module duplicates the
quantize/checksum functions from ``ml/determinism.py`` (F7 frozen, OE-11 isolation).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Final

QUANTIZE_PRECISION: Final[int] = 8
# Decimal("0.00000001") — the rounding quantum for Numeric(20,8).
_QUANTUM = Decimal((0, (1,), -QUANTIZE_PRECISION))


def quantize_metric(value: Real) -> Decimal:
    """Round ``value`` to a ``Decimal`` with 8 fraction digits (Numeric(20,8)).

    Quantizes via ``str`` (exact round-trip, no binary-float artifacts), matching
    design ``Decimal(str(x)).quantize("0.00000001")``.
    """
    return Decimal(str(value)).quantize(_QUANTUM)


def compute_metrics_checksum(metrics: Mapping[str, Real]) -> str:
    """SHA-256 over canonical JSON of the Decimal-QUANTIZED metric payload.

    Quantization happens before serialization: the digest depends only on the
    quantized values, so two raw floats that quantize identically yield the same
    checksum and raw floats never feed the digest (OE-07).
    """
    quantized = {name: str(quantize_metric(value)) for name, value in metrics.items()}
    canonical = json.dumps(quantized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["QUANTIZE_PRECISION", "quantize_metric", "compute_metrics_checksum"]
