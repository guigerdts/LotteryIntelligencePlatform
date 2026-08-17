"""Decimal formatting (A-03): 0.12345678 exact; NULL -> 'sin datos'."""

from __future__ import annotations

from decimal import Decimal

from backend.app.ai.generators import format_decimal, format_optional


def test_format_decimal_exact_fraction() -> None:
    assert format_decimal(Decimal("0.12345678")) == "0.12345678"


def test_format_decimal_normalizes_trailing_zeros() -> None:
    assert format_decimal(Decimal("1.50")) == "1.5"


def test_format_optional_none_is_sin_datos() -> None:
    assert format_optional(None) == "sin datos"


def test_format_optional_preserves_decimal() -> None:
    assert format_optional(Decimal("9.75")) == "9.75"
