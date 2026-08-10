"""Determinism context and metric quantisation (BTE-05, BTE-08).

Provides a ``DeterminismContext`` that encapsulates seed-based RNG state
for reproducible backtesting, and a ``quantize_metric`` helper that
ensures all metric values are Decimal(20,8).
"""

from __future__ import annotations

import random
from decimal import ROUND_HALF_UP, Decimal


class DeterminismContext:
    """Seed management for reproducible backtests (BTE-05).

    Wraps both a ``random.Random`` instance and an optional NumPy RNG
    (imported lazily) behind a single seed so that every stochastic
    decision in a backtest run can be reproduced.

    Usage::

        ctx = DeterminismContext(seed=42)
        rng = ctx.get_python_rng()
        value = rng.random()
    """

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._python_rng = random.Random(seed)
        self._numpy_rng: object | None = None  # lazy

    @property
    def seed(self) -> int:
        return self._seed

    def get_python_rng(self) -> random.Random:
        """Return the deterministic ``random.Random`` instance."""
        return self._python_rng

    def get_numpy_rng(self) -> object:
        """Return the deterministic NumPy Generator (lazy import).

        NumPy is an optional dependency; the import happens only when
        this method is first called, keeping the module importable
        without NumPy installed.
        """
        if self._numpy_rng is None:
            import numpy as np

            self._numpy_rng = np.random.default_rng(self._seed)
        return self._numpy_rng


def quantize_metric(value: float | int | Decimal) -> Decimal:
    """Quantize *value* to ``Decimal(20,8)`` (BTE-08).

    >>> quantize_metric(0.123456789)
    Decimal('0.12345679')
    >>> quantize_metric(100)
    Decimal('100.00000000')
    """
    if isinstance(value, Decimal):
        d = value
    else:
        d = Decimal(str(value))
    return d.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
