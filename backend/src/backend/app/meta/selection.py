"""Selection logic for Meta Learning module.

Selects top-K models from a ranking where score >= min_score (META-006).
"""

from __future__ import annotations

from backend.app.meta.types import RankingEntry, SelectionEntry


def select_top_k(
    ranking_entries: list[RankingEntry],
    top_k: int = 5,
    min_score: float = 0.0,
) -> list[SelectionEntry]:
    """Select top-K models from ranking entries (META-006, META-020).

    Filters by min_score threshold, then takes top_k entries.
    Returns fewer than top_k if insufficient qualifying entries.

    Args:
        ranking_entries: Sorted ranking entries (descending by score).
        top_k: Maximum number to select (default 5, range 1-20).
        min_score: Minimum score threshold (default 0.0).

    Returns:
        List of SelectionEntry with sequential rank positions.
    """
    selected = []
    rank = 1
    for entry in ranking_entries:
        if entry.score < min_score:
            continue
        selected.append(
            SelectionEntry(
                model_id=entry.model_id,
                engine_type=entry.engine_type,
                rank=rank,
                score=entry.score,
            )
        )
        rank += 1
        if len(selected) >= top_k:
            break
    return selected
