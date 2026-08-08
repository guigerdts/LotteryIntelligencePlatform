"""Co-occurrence engine (GES-01, GM-01): joint pair counts from draw history.

Computes the symmetric co-occurrence matrix for all number pairs. Supports
full-history (default) and rolling-window (versioned param). Integer arithmetic
only — no float leakage (REQ-01, D8).

Algorithm (GES-01):
- For each draw, count co-occurrences of all number pairs
- Full-history: accumulate from first draw
- Rolling: window of last N draws
- Window param is part of fingerprint (REQ-06)
- Same input + params + version ⇒ same output (byte-identical)

Constraints:
- Matrix is symmetric: M[i][j] = M[j][i]
- All counts are integers
- Deterministic output
"""

from __future__ import annotations

from typing import Protocol


class DrawReader(Protocol):
    """Protocol for reading draws from the database.

    Mirrors the F3/F5 DrawReader pattern (A9): the graph engine reads
    draws only through this protocol, never importing F3/F4/F5 internals.
    """

    def read_draw_numbers(self, draw_id: int) -> list[int]:
        """Return sorted list of main numbers for a draw (no super_number)."""
        ...

    def get_draw_ids(self, lottery_id: int, limit: int | None = None) -> list[int]:
        """Return draw IDs in chronological order for a lottery."""
        ...


def compute_cooccurrence(
    draw_numbers: list[list[int]],
    window: int | None = None,
) -> dict[tuple[int, int], int]:
    """Compute co-occurrence matrix from draw numbers.

    Args:
        draw_numbers: List of draws, each a sorted list of main numbers.
        window: If None, full-history. If int, last N draws only.

    Returns:
        Symmetric dict of {(i, j): count} where i < j.
        All counts are integers (no float).

    Raises:
        ValueError: If window <= 0 or window > len(draw_numbers).
    """
    if window is not None:
        if window <= 0:
            raise ValueError(f"window must be positive, got {window}")
        draw_numbers = draw_numbers[-window:]

    cooccurrence: dict[tuple[int, int], int] = {}

    for draw in draw_numbers:
        sorted_draw = sorted(draw)
        for i_idx in range(len(sorted_draw)):
            for j_idx in range(i_idx + 1, len(sorted_draw)):
                pair = (sorted_draw[i_idx], sorted_draw[j_idx])
                cooccurrence[pair] = cooccurrence.get(pair, 0) + 1

    return cooccurrence


def cooccurrence_to_matrix(
    cooccurrence: dict[tuple[int, int], int],
) -> dict[int, dict[int, int]]:
    """Convert co-occurrence dict to symmetric matrix representation.

    Args:
        cooccurrence: Dict of {(i, j): count} where i < j.

    Returns:
        Nested dict: {node: {neighbor: count}} with full symmetry.
    """
    matrix: dict[int, dict[int, int]] = {}

    for (i, j), count in cooccurrence.items():
        if i not in matrix:
            matrix[i] = {}
        if j not in matrix:
            matrix[j] = {}
        matrix[i][j] = count
        matrix[j][i] = count

    return matrix
