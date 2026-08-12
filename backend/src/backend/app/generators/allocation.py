"""Allocation module — GEN-004 exact integer micro-unit arithmetic.

Distributes a fixed ``count`` across scored entries using integer
micro-units (``SCORE_SCALE = 10**6``) so that ``Σcᵢ == count`` is
guaranteed without float drift.

Procedure:
  1. Scale scores to int micros (representation conversion).
  2. Floor division ``micros * count // total_micros``.
  3. Distribute remainder by descending micro-unit score, tie by lower rank.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.errors import GenServiceError

SCORE_SCALE: int = 10**6
"""Fixed scale factor for integer micro-unit representation."""


@dataclass(frozen=True)
class SelectionEntry:
    """Lightweight entry for allocation — score and rank only."""

    score: float
    rank: int


def allocate_count(entries: list[SelectionEntry], count: int) -> list[tuple[int, int]]:
    """Return ``[(entry_index, allocated_count)]`` with ``Σcᵢ == count`` guaranteed.

    Uses exact integer micro-unit arithmetic (GEN-004):
      1. Scale each score to int micros (``int(round(score * SCORE_SCALE))``).
      2. Floor-divide ``micros * count // total_micros`` per entry.
      3. Distribute remainder by descending micro-unit score, ties by lower rank.

    Raises ``GenServiceError("GEN_COUNT_INVALID")`` when total score is zero.
    """
    if not entries:
        return []

    total_score = sum(e.score for e in entries)
    if total_score == 0:
        raise GenServiceError(GenServiceError.GEN_COUNT_INVALID, "total score is zero")

    # Step 1: scale scores to integer micro-units (representation conversion).
    score_micros = [int(round(e.score * SCORE_SCALE)) for e in entries]
    total_micros = sum(score_micros)

    # Step 2: floor division — no float arithmetic.
    allocations: list[tuple[int, int]] = []
    remainder = count
    for i, micros in enumerate(score_micros):
        c = micros * count // total_micros
        allocations.append((i, c))
        remainder -= c

    # Step 3: distribute remainder by descending micro-unit score (tie: lower rank).
    ranked = sorted(range(len(entries)), key=lambda i: (-score_micros[i], entries[i].rank))
    for idx in ranked:
        if remainder <= 0:
            break
        allocations[idx] = (allocations[idx][0], allocations[idx][1] + 1)
        remainder -= 1

    return allocations
