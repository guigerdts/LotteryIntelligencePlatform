"""Determinism contract for the DL engine (DLE-07 / D-A2).

``configure_deterministic_torch`` sets seed 0, enables deterministic algorithms,
and pins to 1 CPU thread.  Every metric is quantized to ``Decimal(20,8)`` BEFORE
any checksum digest or persistence — a raw float never feeds a fingerprint,
checksum, or stored row (float red line, DLE-08).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from numbers import Real
from typing import Final

import torch

QUANTIZE_PRECISION: Final[int] = 8
# Decimal("0.00000001") — the rounding quantum for Numeric(20,8).
_QUANTUM = Decimal((0, (1,), -QUANTIZE_PRECISION))

# Default seed for DL determinism (D-A2).
DL_SEED: Final[int] = 0


def configure_deterministic_torch(seed: int = DL_SEED) -> None:
    """Configure PyTorch for same-env byte-identical CPU determinism (DLE-07).

    Sets the global seed, enables deterministic algorithms (fail-fast if an
    unsupported op is used), and pins to a single CPU thread.  float32 is
    enforced by the engine's tensor construction (D-A8).

    Raises ``RuntimeError`` if a required deterministic op is unavailable.
    """
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def quantize_metric(value: Real) -> Decimal:
    """Round ``value`` to a ``Decimal`` with 8 fraction digits (Numeric(20,8)).

    Quantizes via ``str`` (exact round-trip, no binary-float artifacts), matching
    design D-A7 ``Decimal(str(x)).quantize("0.00000001")``.
    """
    return Decimal(str(value)).quantize(_QUANTUM)


def compute_metrics_checksum(metrics: Mapping[str, Real]) -> str:
    """SHA-256 over canonical JSON of the Decimal-QUANTIZED metric payload.

    Quantization happens before serialization: the digest depends only on the
    quantized values, so two raw floats that quantize identically yield the same
    checksum and raw floats never feed the digest (DLE-08 scenario "float
    excluded from checksum").
    """
    quantized = {name: str(quantize_metric(value)) for name, value in metrics.items()}
    canonical = json.dumps(quantized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "DL_SEED",
    "QUANTIZE_PRECISION",
    "configure_deterministic_torch",
    "compute_metrics_checksum",
    "quantize_metric",
]
