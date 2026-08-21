"""Tests for meta.selection — top-K selection with threshold filtering.

Spec refs: META-006 (selection), META-020 (top-K defaults).
Design refs: Selection section.
"""

from __future__ import annotations

from backend.app.meta.selection import select_top_k
from backend.app.meta.types import RankingEntry, SelectionEntry


def _make_entries(count: int, base_score: float = 0.5) -> list[RankingEntry]:
    """Helper: create N ranking entries with decreasing scores."""
    return [
        RankingEntry(
            model_id=f"model-{i}",
            engine_type="ml",
            score=base_score + (count - i) * 0.1,
            metrics={},
        )
        for i in range(count)
    ]


class TestSelectTopK:
    """select_top_k — top-K selection (META-006, META-020)."""

    def test_top_k_correct(self) -> None:
        entries = _make_entries(10, base_score=0.1)
        selected = select_top_k(entries, top_k=5)
        assert len(selected) == 5
        # Verify descending order
        scores = [s.score for s in selected]
        assert scores == sorted(scores, reverse=True)

    def test_returns_selection_entry_dataclass(self) -> None:
        entries = _make_entries(3, base_score=0.5)
        selected = select_top_k(entries, top_k=5)
        assert isinstance(selected[0], SelectionEntry)
        assert selected[0].model_id == "model-0"
        assert selected[0].rank == 1

    def test_threshold_filtering(self) -> None:
        """Only models with score >= min_score are selected (META-006)."""
        entries = [
            RankingEntry("a", "ml", 0.9, {}),
            RankingEntry("b", "ml", 0.5, {}),
            RankingEntry("c", "ml", 0.3, {}),
            RankingEntry("d", "ml", 0.1, {}),
        ]
        selected = select_top_k(entries, top_k=10, min_score=0.5)
        assert len(selected) == 2
        model_ids = [s.model_id for s in selected]
        assert "a" in model_ids
        assert "b" in model_ids
        assert "c" not in model_ids
        assert "d" not in model_ids

    def test_insufficient_qualifying_returns_fewer(self) -> None:
        """Returns fewer than K if insufficient qualifying (META-006)."""
        entries = [
            RankingEntry("a", "ml", 0.9, {}),
            RankingEntry("b", "ml", 0.8, {}),
        ]
        selected = select_top_k(entries, top_k=5, min_score=0.0)
        assert len(selected) == 2

    def test_default_k_is_five(self) -> None:
        entries = _make_entries(10, base_score=0.1)
        selected = select_top_k(entries)
        assert len(selected) == 5

    def test_default_min_score_is_zero(self) -> None:
        entries = [
            RankingEntry("a", "ml", 0.9, {}),
            RankingEntry("b", "ml", 0.0, {}),
            RankingEntry("c", "ml", -0.1, {}),
        ]
        selected = select_top_k(entries, top_k=10)
        # min_score=0.0, so only a and b qualify (b=0.0 >= 0.0)
        assert len(selected) == 2

    def test_empty_entries(self) -> None:
        selected = select_top_k([], top_k=5)
        assert selected == []

    def test_rank_positions_are_sequential(self) -> None:
        entries = _make_entries(5, base_score=0.5)
        selected = select_top_k(entries, top_k=3)
        ranks = [s.rank for s in selected]
        assert ranks == [1, 2, 3]

    def test_k_greater_than_entries(self) -> None:
        entries = _make_entries(2, base_score=0.5)
        selected = select_top_k(entries, top_k=10)
        assert len(selected) == 2

    def test_min_score_excludes_all(self) -> None:
        entries = _make_entries(5, base_score=0.1)
        selected = select_top_k(entries, top_k=5, min_score=1.0)
        assert selected == []
