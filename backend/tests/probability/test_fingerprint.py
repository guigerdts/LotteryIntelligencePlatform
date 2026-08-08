"""Probability input fingerprint tests (PES-05): canonical SHA-256 over inputs.

The Probability Engine fingerprint MUST be a canonical SHA-256 hex digest over
compact JSON (``sort_keys=True``, ``separators=(",", ":")``) so equal inputs
yield byte-identical digests regardless of dict insertion order. Decimal values
must be normalized to canonical strings — float never enters the digest (PES-05).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.probability.fingerprint import probability_input_fingerprint


def test_fingerprint_stable_for_equal_inputs() -> None:
    """Equal input payloads (any insertion order) yield identical 64-char hex."""
    a = probability_input_fingerprint(
        {"draws": {"from": 1, "to": 5}, "models": ["hypergeometric"], "stats": None}
    )
    b = probability_input_fingerprint(
        {"stats": None, "models": ["hypergeometric"], "draws": {"to": 5, "from": 1}}
    )
    assert a == b
    assert len(a) == 64
    assert all(c in "0123456789abcdef" for c in a)


def test_fingerprint_changes_when_input_changes() -> None:
    """Different inputs (draw range, model set, stats) MUST change the digest."""
    base = {"draws": {"from": 1, "to": 5}, "models": ["hypergeometric"], "stats": None}
    other = {"draws": {"from": 1, "to": 6}, "models": ["hypergeometric"], "stats": None}
    assert probability_input_fingerprint(base) != probability_input_fingerprint(other)


def test_fingerprint_handles_decimal_and_nested_values() -> None:
    """Decimal and nested mappings normalize to stable JSON (never float)."""
    payload = {
        "models": [{"id": "binomial", "params": {"p": Decimal("0.5")}}],
        "stats": {"checksum": "abcdef"},
    }
    first = probability_input_fingerprint(payload)
    second = probability_input_fingerprint(
        {"stats": {"checksum": "abcdef"}, "models": [{"params": {"p": "0.5"}, "id": "binomial"}]}
    )
    assert first == second