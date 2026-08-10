"""Tests for DeterminismContext and quantize_metric (BTE-05, BTE-08).

Verifies seed-based reproducibility and Decimal(20,8) quantisation.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.backtesting.determinism import DeterminismContext, quantize_metric


class TestDeterminismContext:
    """Seed-based reproducibility (BTE-05)."""

    def test_same_seed_same_rng_sequence(self) -> None:
        ctx1 = DeterminismContext(seed=42)
        ctx2 = DeterminismContext(seed=42)
        values1 = [ctx1.get_python_rng().random() for _ in range(10)]
        values2 = [ctx2.get_python_rng().random() for _ in range(10)]
        assert values1 == values2

    def test_different_seed_different_sequence(self) -> None:
        ctx1 = DeterminismContext(seed=42)
        ctx2 = DeterminismContext(seed=99)
        values1 = [ctx1.get_python_rng().random() for _ in range(10)]
        values2 = [ctx2.get_python_rng().random() for _ in range(10)]
        assert values1 != values2

    def test_seed_property(self) -> None:
        ctx = DeterminismContext(seed=7)
        assert ctx.seed == 7

    def test_python_rng_is_random_instance(self) -> None:
        import random

        ctx = DeterminismContext(seed=1)
        assert isinstance(ctx.get_python_rng(), random.Random)

    def test_numpy_rng_lazy_import(self) -> None:
        ctx = DeterminismContext(seed=1)
        rng = ctx.get_numpy_rng()
        # Should be a numpy Generator
        import numpy as np

        assert isinstance(rng, np.random.Generator)

    def test_numpy_rng_same_seed_reproducible(self) -> None:
        ctx1 = DeterminismContext(seed=42)
        ctx2 = DeterminismContext(seed=42)
        values1 = [float(ctx1.get_numpy_rng().random()) for _ in range(5)]
        values2 = [float(ctx2.get_numpy_rng().random()) for _ in range(5)]
        assert values1 == values2


class TestQuantizeMetric:
    """Decimal(20,8) quantisation (BTE-08)."""

    def test_quantize_float(self) -> None:
        result = quantize_metric(0.123456789)
        assert result == Decimal("0.12345679")
        assert isinstance(result, Decimal)

    def test_quantize_int(self) -> None:
        result = quantize_metric(100)
        assert result == Decimal("100.00000000")

    def test_quantize_decimal(self) -> None:
        result = quantize_metric(Decimal("0.123456789"))
        assert result == Decimal("0.12345679")

    def test_quantize_already_precision(self) -> None:
        result = quantize_metric(Decimal("0.12345678"))
        assert result == Decimal("0.12345678")

    def test_quantize_zero(self) -> None:
        result = quantize_metric(0)
        assert result == Decimal("0.00000000")

    def test_quantize_large_number(self) -> None:
        result = quantize_metric(99999999.99999999)
        assert result == Decimal("99999999.99999999")
