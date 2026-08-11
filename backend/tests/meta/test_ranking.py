"""Tests for meta.ranking — stable sort and fingerprint computation.

Spec refs: META-005 (ranking), META-007 (idempotency), META-009 (fingerprint),
NFR-META-01 (determinism), NFR-META-10 (stable sort).
Design refs: Ranking section.
"""

from __future__ import annotations

import pytest

from backend.app.meta.ranking import build_ranking_entries, compute_fingerprint
from backend.app.meta.types import RankingEntry


class TestBuildRankingEntries:
    """build_ranking_entries — descending stable sort (META-005, NFR-META-10)."""

    def test_descending_order(self) -> None:
        scored = [
            {"model_id": "a", "engine_type": "ml", "score": 0.7, "metrics": {}},
            {"model_id": "b", "engine_type": "ml", "score": 0.9, "metrics": {}},
            {"model_id": "c", "engine_type": "ml", "score": 0.8, "metrics": {}},
            {"model_id": "d", "engine_type": "ml", "score": 0.6, "metrics": {}},
        ]
        entries = build_ranking_entries(scored)
        scores = [e.score for e in entries]
        assert scores == [pytest.approx(0.9), pytest.approx(0.8), pytest.approx(0.7), pytest.approx(0.6)]

    def test_stable_sort_preserves_order(self) -> None:
        """Equal scores preserve insertion order (NFR-META-10, stable sort)."""
        scored = [
            {"model_id": "first", "engine_type": "ml", "score": 0.8, "metrics": {}},
            {"model_id": "second", "engine_type": "ml", "score": 0.8, "metrics": {}},
            {"model_id": "third", "engine_type": "ml", "score": 0.8, "metrics": {}},
        ]
        entries = build_ranking_entries(scored)
        model_ids = [e.model_id for e in entries]
        assert model_ids == ["first", "second", "third"]

    def test_returns_ranking_entry_dataclass(self) -> None:
        scored = [
            {"model_id": "a", "engine_type": "ml", "score": 0.8, "metrics": {"hit_rate": 0.9}},
        ]
        entries = build_ranking_entries(scored)
        assert len(entries) == 1
        assert isinstance(entries[0], RankingEntry)
        assert entries[0].model_id == "a"
        assert entries[0].engine_type == "ml"
        assert entries[0].score == pytest.approx(0.8)
        assert entries[0].metrics == {"hit_rate": 0.9}

    def test_empty_input(self) -> None:
        entries = build_ranking_entries([])
        assert entries == []

    def test_single_entry(self) -> None:
        scored = [
            {"model_id": "solo", "engine_type": "dl", "score": 0.5, "metrics": {}},
        ]
        entries = build_ranking_entries(scored)
        assert len(entries) == 1
        assert entries[0].model_id == "solo"

    def test_cross_engine_sort(self) -> None:
        """Different engine types sort together by score."""
        scored = [
            {"model_id": "bt-1", "engine_type": "backtesting", "score": 0.6, "metrics": {}},
            {"model_id": "ml-1", "engine_type": "ml", "score": 0.9, "metrics": {}},
            {"model_id": "opt-1", "engine_type": "optimization", "score": 0.7, "metrics": {}},
        ]
        entries = build_ranking_entries(scored)
        model_ids = [e.model_id for e in entries]
        assert model_ids == ["ml-1", "opt-1", "bt-1"]


class TestComputeFingerprint:
    """compute_fingerprint — SHA-256 idempotency key (META-007, META-009)."""

    def test_deterministic(self) -> None:
        entries = [
            RankingEntry("a", "ml", 0.8, {"hit_rate": 0.9}),
            RankingEntry("b", "ml", 0.6, {"hit_rate": 0.5}),
        ]
        fp1 = compute_fingerprint(1, "abc123", entries)
        fp2 = compute_fingerprint(1, "abc123", entries)
        assert fp1 == fp2

    def test_different_data_produces_different_fingerprint(self) -> None:
        """META-009: different data → different fingerprint."""
        entries_a = [RankingEntry("a", "ml", 0.8, {})]
        entries_b = [RankingEntry("a", "ml", 0.9, {})]
        fp_a = compute_fingerprint(1, "abc", entries_a)
        fp_b = compute_fingerprint(1, "abc", entries_b)
        assert fp_a != fp_b

    def test_different_context_hash_produces_different_fingerprint(self) -> None:
        entries = [RankingEntry("a", "ml", 0.8, {})]
        fp1 = compute_fingerprint(1, "hash1", entries)
        fp2 = compute_fingerprint(1, "hash2", entries)
        assert fp1 != fp2

    def test_different_lottery_id_produces_different_fingerprint(self) -> None:
        entries = [RankingEntry("a", "ml", 0.8, {})]
        fp1 = compute_fingerprint(1, "abc", entries)
        fp2 = compute_fingerprint(2, "abc", entries)
        assert fp1 != fp2

    def test_is_sha256_hex(self) -> None:
        entries = [RankingEntry("a", "ml", 0.8, {})]
        fp = compute_fingerprint(1, "abc", entries)
        assert len(fp) == 64
        # Valid hex characters only
        assert all(c in "0123456789abcdef" for c in fp)

    def test_empty_entries(self) -> None:
        fp = compute_fingerprint(1, "abc", [])
        assert len(fp) == 64

    def test_order_insensitive_for_entries(self) -> None:
        """Same entries in different order produce same fingerprint."""
        entries_a = [
            RankingEntry("a", "ml", 0.8, {}),
            RankingEntry("b", "ml", 0.6, {}),
        ]
        entries_b = [
            RankingEntry("b", "ml", 0.6, {}),
            RankingEntry("a", "ml", 0.8, {}),
        ]
        fp_a = compute_fingerprint(1, "abc", entries_a)
        fp_b = compute_fingerprint(1, "abc", entries_b)
        assert fp_a == fp_b
