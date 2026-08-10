"""Unit tests for dl.determinism — seed, algorithms, quantize, checksum (DLE-07)."""

from __future__ import annotations

from decimal import Decimal


def test_configure_deterministic_torch_sets_seed() -> None:
    """configure_deterministic_torch sets torch manual seed (DLE-07)."""
    import torch

    from backend.app.dl.determinism import DL_SEED, configure_deterministic_torch

    configure_deterministic_torch()
    # After seeding, a fresh generator should produce the same stream.
    gen1 = torch.Generator()
    gen1.manual_seed(DL_SEED)
    expected = torch.rand(5, generator=gen1)

    configure_deterministic_torch()
    gen2 = torch.Generator()
    gen2.manual_seed(DL_SEED)
    actual = torch.rand(5, generator=gen2)
    assert torch.equal(expected, actual)


def test_configure_deterministic_torch_single_thread() -> None:
    """configure_deterministic_torch pins to 1 CPU thread (DLE-07)."""
    import torch

    from backend.app.dl.determinism import configure_deterministic_torch

    configure_deterministic_torch()
    assert torch.get_num_threads() == 1


def test_quantize_metric_rounds_to_8_digits() -> None:
    """quantize_metric rounds to Decimal(20,8) (D-A7)."""
    from backend.app.dl.determinism import quantize_metric

    result = quantize_metric(0.123456789)
    assert isinstance(result, Decimal)
    assert result == Decimal("0.12345679")
    assert result.as_tuple().exponent == -8


def test_quantize_metric_exact_representable() -> None:
    """quantize_metric preserves exact representable values."""
    from backend.app.dl.determinism import quantize_metric

    result = quantize_metric(0.5)
    assert result == Decimal("0.50000000")


def test_quantize_metric_integer() -> None:
    """quantize_metric handles integers."""
    from backend.app.dl.determinism import quantize_metric

    result = quantize_metric(1)
    assert result == Decimal("1.00000000")


def test_compute_metrics_checksum_deterministic() -> None:
    """compute_metrics_checksum produces identical output for identical input."""
    from backend.app.dl.determinism import compute_metrics_checksum

    metrics = {"accuracy": 0.95, "f1": 0.87}
    h1 = compute_metrics_checksum(metrics)
    h2 = compute_metrics_checksum(metrics)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_compute_metrics_checksum_quantized() -> None:
    """compute_metrics_checksum quantizes before hashing (DLE-08)."""
    from backend.app.dl.determinism import compute_metrics_checksum

    # Both values round DOWN to 0.12345678 at Decimal(20,8)
    h1 = compute_metrics_checksum({"acc": 0.123456781})
    h2 = compute_metrics_checksum({"acc": 0.123456784})
    assert h1 == h2


def test_compute_metrics_checksum_order_independent() -> None:
    """compute_metrics_checksum is order-independent (sort_keys=True)."""
    from backend.app.dl.determinism import compute_metrics_checksum

    h1 = compute_metrics_checksum({"a": 0.1, "b": 0.2})
    h2 = compute_metrics_checksum({"b": 0.2, "a": 0.1})
    assert h1 == h2
