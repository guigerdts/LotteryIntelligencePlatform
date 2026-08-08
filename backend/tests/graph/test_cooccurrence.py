"""Tests for co-occurrence engine (GES-01, GM-01, Task 3).

Tests cover:
- Basic co-occurrence computation
- Matrix symmetry (REQ-02)
- Integer arithmetic (no float)
- Full-history and rolling-window
- Byte-identical reruns (determinism)
- Edge cases (empty, single draw)
"""

from __future__ import annotations

from backend.app.graph.cooccurrence import compute_cooccurrence, cooccurrence_to_matrix


class TestCooccurrence:
    """Tests for co-occurrence computation."""

    def test_basic_cooccurrence(self) -> None:
        """Basic co-occurrence counts pairs correctly."""
        draws = [
            [1, 2, 3],
            [1, 2, 4],
            [2, 3, 4],
        ]
        result = compute_cooccurrence(draws)

        # Pair (1,2) appears in draws 0,1 = 2 times
        assert result[(1, 2)] == 2
        # Pair (1,3) appears in draw 0 = 1 time
        assert result[(1, 3)] == 1
        # Pair (1,4) appears in draw 1 = 1 time
        assert result[(1, 4)] == 1
        # Pair (2,3) appears in draws 0,2 = 2 times
        assert result[(2, 3)] == 2
        # Pair (2,4) appears in draws 1,2 = 2 times
        assert result[(2, 4)] == 2
        # Pair (3,4) appears in draw 2 = 1 time
        assert result[(3, 4)] == 1

    def test_symmetry(self) -> None:
        """Co-occurrence matrix is symmetric (REQ-02)."""
        draws = [[1, 2, 3], [4, 5, 6]]
        result = compute_cooccurrence(draws)

        # All pairs should have i < j
        for (i, j) in result:
            assert i < j, f"Pair ({i}, {j}) not in canonical form"

    def test_integer_arithmetic(self) -> None:
        """All counts are integers (no float, D8)."""
        draws = [[1, 2, 3], [1, 2, 4]]
        result = compute_cooccurrence(draws)

        for count in result.values():
            assert isinstance(count, int)
            assert count > 0

    def test_full_history_default(self) -> None:
        """Full-history is default (window=None)."""
        draws = [[1, 2], [3, 4], [1, 3]]
        result_full = compute_cooccurrence(draws, window=None)
        result_explicit = compute_cooccurrence(draws)

        assert result_full == result_explicit

    def test_rolling_window(self) -> None:
        """Rolling window uses only last N draws."""
        draws = [[1, 2], [3, 4], [1, 3]]
        result = compute_cooccurrence(draws, window=2)

        # Only draws 1,2 are used
        assert (1, 3) in result  # from draw 2
        assert result[(1, 3)] == 1
        # (1,2) from draw 0 is NOT included
        assert (1, 2) not in result

    def test_window_larger_than_history(self) -> None:
        """Window larger than history uses all draws."""
        draws = [[1, 2], [3, 4]]
        result = compute_cooccurrence(draws, window=10)

        assert (1, 2) in result
        assert (3, 4) in result

    def test_window_zero_raises(self) -> None:
        """Window=0 raises ValueError."""
        draws = [[1, 2]]
        try:
            compute_cooccurrence(draws, window=0)
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "window must be positive" in str(e)

    def test_window_negative_raises(self) -> None:
        """Window=-1 raises ValueError."""
        draws = [[1, 2]]
        try:
            compute_cooccurrence(draws, window=-1)
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "window must be positive" in str(e)

    def test_empty_draws(self) -> None:
        """Empty draw list returns empty co-occurrence."""
        result = compute_cooccurrence([])
        assert result == {}

    def test_single_draw(self) -> None:
        """Single draw computes pairs correctly."""
        draws = [[1, 2, 3, 4, 5]]
        result = compute_cooccurrence(draws)

        # C(5,2) = 10 pairs
        assert len(result) == 10
        for count in result.values():
            assert count == 1

    def test_deterministic_rerun(self) -> None:
        """Same input produces same output (byte-identical, REQ-01)."""
        draws = [[1, 2, 3], [4, 5, 6], [1, 4, 7]]

        result1 = compute_cooccurrence(draws)
        result2 = compute_cooccurrence(draws)

        assert result1 == result2
        assert list(result1.keys()) == list(result2.keys())

    def test_sorted_input(self) -> None:
        """Unsorted draw numbers are handled correctly."""
        draws = [[3, 1, 2], [4, 2, 1]]
        result = compute_cooccurrence(draws)

        # Pair (1,2) appears in both draws
        assert result[(1, 2)] == 2
        # Pair (1,3) appears in draw 0
        assert result[(1, 3)] == 1

    def test_cooccurrence_to_matrix(self) -> None:
        """Matrix conversion produces symmetric adjacency."""
        cooccurrence = {(1, 2): 3, (2, 3): 1, (1, 3): 2}
        matrix = cooccurrence_to_matrix(cooccurrence)

        # Check symmetry
        assert matrix[1][2] == matrix[2][1] == 3
        assert matrix[2][3] == matrix[3][2] == 1
        assert matrix[1][3] == matrix[3][1] == 2
