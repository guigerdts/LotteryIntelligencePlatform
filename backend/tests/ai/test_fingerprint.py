"""Fingerprint (A-02): identical for equal inputs, differs on any change."""

from __future__ import annotations

from decimal import Decimal

from backend.app.ai.fingerprint import compute_ai_fingerprint


def test_identical_for_equal_inputs_any_order() -> None:
    inputs = {"lottery_code": "ISO", "rows": [1, 2]}
    first = compute_ai_fingerprint("1.0.0", "explain", inputs)
    second = compute_ai_fingerprint("1.0.0", "explain", {"rows": [1, 2], "lottery_code": "ISO"})
    assert first == second
    assert len(first) == 64


def test_differs_on_version_function_inputs() -> None:
    base = {"lottery_code": "ISO"}
    digest = compute_ai_fingerprint("1.0.0", "explain", base)
    assert compute_ai_fingerprint("2.0.0", "explain", base) != digest
    assert compute_ai_fingerprint("1.0.0", "report", base) != digest
    assert compute_ai_fingerprint("1.0.0", "explain", {"n": 2}) != digest


def test_decimal_normalizes_to_str() -> None:
    assert compute_ai_fingerprint("1.0.0", "explain", {"v": Decimal("0.5")}) == (
        compute_ai_fingerprint("1.0.0", "explain", {"v": "0.5"})
    )
