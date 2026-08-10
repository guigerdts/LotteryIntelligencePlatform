"""Tests for opt/determinism — Decimal quantization and checksum (OE-06/07)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.opt.determinism import (
    QUANTIZE_PRECISION,
    compute_metrics_checksum,
    quantize_metric,
)


def test_quantize_precision() -> None:
    """QUANTIZE_PRECISION is 8 (Numeric(20,8))."""
    assert QUANTIZE_PRECISION == 8


def test_quantize_metric_basic() -> None:
    """quantize_metric rounds to 8 decimal places."""
    result = quantize_metric(0.123456789)
    assert result == Decimal("0.12345679")
    assert isinstance(result, Decimal)


def test_quantize_metric_exact() -> None:
    """quantize_metric preserves exact values."""
    result = quantize_metric(0.5)
    assert result == Decimal("0.50000000")


def test_quantize_metric_integer() -> None:
    """quantize_metric handles integers."""
    result = quantize_metric(1)
    assert result == Decimal("1.00000000")


def test_quantize_metric_string_input() -> None:
    """quantize_metric handles string input via Decimal."""
    result = quantize_metric("0.123456789")
    assert result == Decimal("0.12345679")


def test_checksum_deterministic() -> None:
    """Same metrics produce identical checksum."""
    metrics = {"f1": 0.85, "accuracy": 0.92}
    c1 = compute_metrics_checksum(metrics)
    c2 = compute_metrics_checksum(metrics)
    assert c1 == c2
    assert len(c1) == 64  # SHA-256 hex


def test_checksum_quantized() -> None:
    """Checksum depends on quantized values, not raw floats."""
    # These quantize to the same value
    c1 = compute_metrics_checksum({"f1": 0.850000001})
    c2 = compute_metrics_checksum({"f1": 0.850000002})
    assert c1 == c2


def test_checksum_changes_on_value_change() -> None:
    """Different metric values produce different checksum."""
    c1 = compute_metrics_checksum({"f1": 0.85})
    c2 = compute_metrics_checksum({"f1": 0.86})
    assert c1 != c2


def test_checksum_key_order_irrelevant() -> None:
    """Different key ordering produces identical checksum (sort_keys=True)."""
    c1 = compute_metrics_checksum({"b": 0.5, "a": 0.8})
    c2 = compute_metrics_checksum({"a": 0.8, "b": 0.5})
    assert c1 == c2
