"""Tests for meta.context — context resolution and hash computation.

Spec refs: META-003 (context hash determinism), META-011 (leakage prevention).
Design refs: Context Resolution section.
"""

from __future__ import annotations

import hashlib
import json

from backend.app.meta.context import compute_context_hash, resolve_context_vector
from backend.app.meta.types import ContextVector


class TestComputeContextHash:
    """compute_context_hash — deterministic SHA-256 over context vector."""

    def test_same_inputs_same_hash(self) -> None:
        cv = ContextVector(1, 100, 200, 50, 10, "backtesting")
        h1 = compute_context_hash(cv)
        h2 = compute_context_hash(cv)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_is_sha256_hex(self) -> None:
        cv = ContextVector(1, 100, 200, 50, 10, "backtesting")
        h = compute_context_hash(cv)
        # Verify against manual SHA-256
        payload = json.dumps(
            {
                "lottery_id": 1,
                "draws_from": 100,
                "draws_to": 200,
                "cut": 50,
                "window": 10,
                "engine_type": "backtesting",
            },
            sort_keys=True,
        )
        expected = hashlib.sha256(payload.encode()).hexdigest()
        assert h == expected

    def test_different_draws_to_different_hash(self) -> None:
        a = ContextVector(1, 100, 200, 50, 10, "backtesting")
        b = ContextVector(1, 100, 300, 50, 10, "backtesting")
        assert compute_context_hash(a) != compute_context_hash(b)

    def test_different_engine_type_different_hash(self) -> None:
        a = ContextVector(1, 100, 200, 50, 10, "backtesting")
        b = ContextVector(1, 100, 200, 50, 10, "ml")
        assert compute_context_hash(a) != compute_context_hash(b)

    def test_lottery_isolation_different_hash(self) -> None:
        """META-012: no cross-lottery contamination."""
        a = ContextVector(1, 100, 200, 50, 10, "backtesting")
        b = ContextVector(2, 100, 200, 50, 10, "backtesting")
        assert compute_context_hash(a) != compute_context_hash(b)

    def test_none_cut_window_still_hashable(self) -> None:
        cv = ContextVector(1, 100, 200, None, None, "ml")
        h = compute_context_hash(cv)
        assert len(h) == 64


class TestResolveContextVector:
    """resolve_context_vector — reads engine snapshot parameters from DB."""

    def test_importable(self) -> None:
        """Verify the function exists and is callable."""
        assert callable(resolve_context_vector)
