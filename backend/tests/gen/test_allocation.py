"""Tests for generator allocation — GEN-004 exact integer micro-unit arithmetic.

Spec refs: GEN-004 (allocation rule), GEN-013 (errors).
Design refs: GEN-004 Allocation — Exact Integer Micro-Unit Arithmetic.
"""

from __future__ import annotations

import pytest

from backend.app.generators.allocation import SelectionEntry, allocate_count
from backend.app.services.errors import GenServiceError


class TestAllocateCount:
    """allocate_count() — GEN-004 micro-unit integer arithmetic."""

    @pytest.mark.parametrize(
        "scores,count,expected",
        [
            ([0.7, 0.3], 90, [63, 27]),
            ([0.5, 0.3, 0.2], 10, [5, 3, 2]),
            ([0.34, 0.33, 0.33], 10, [4, 3, 3]),
            ([0.999999, 0.000001], 100, [100, 0]),
            ([0.333, 0.333, 0.334], 100, [33, 33, 34]),
        ],
    )
    def test_allocate_count_exact(
        self, scores: list[float], count: int, expected: list[int]
    ) -> None:
        """Every case: sum == count AND sorted matches sorted expected."""
        entries = [SelectionEntry(score=s, rank=i) for i, s in enumerate(scores)]
        result = allocate_count(entries, count)
        allocations = [c for _, c in result]
        assert sum(allocations) == count
        assert sorted(allocations, reverse=True) == sorted(expected, reverse=True)

    def test_precision_regression_07_90(self) -> None:
        """MANDATORY precision regression: [0.7, 0.3] * 90 → [63, 27].

        Catches float drift that [0.5, 0.3, 0.2] * 10 does not.
        round(0.7 * 1e6) = 700000, 700000 * 90 // 1000000 = 63 exactly.
        """
        entries = [SelectionEntry(score=0.7, rank=0), SelectionEntry(score=0.3, rank=1)]
        result = allocate_count(entries, 90)
        allocations = [c for _, c in result]
        assert allocations[0] == 63
        assert allocations[1] == 27
        assert sum(allocations) == 90

    def test_tie_break_by_rank(self) -> None:
        """Equal scores: remainder goes to lower rank first."""
        entries = [
            SelectionEntry(score=0.5, rank=2),
            SelectionEntry(score=0.5, rank=0),
            SelectionEntry(score=0.5, rank=1),
        ]
        result = allocate_count(entries, 10)
        allocations = [c for _, c in result]
        assert sum(allocations) == 10
        # All equal score; remainder=1 goes to rank=0 (entry index 1)
        assert allocations[1] == 4

    def test_single_entry(self) -> None:
        """Single entry gets all count."""
        entries = [SelectionEntry(score=1.0, rank=0)]
        result = allocate_count(entries, 50)
        allocations = [c for _, c in result]
        assert allocations == [50]

    def test_zero_total_score_raises(self) -> None:
        """Total score zero → GenServiceError GEN_COUNT_INVALID."""
        entries = [SelectionEntry(score=0.0, rank=0), SelectionEntry(score=0.0, rank=1)]
        with pytest.raises(GenServiceError) as exc_info:
            allocate_count(entries, 10)
        assert exc_info.value.code == "GEN_COUNT_INVALID"

    def test_count_zero(self) -> None:
        """Count=0: all allocations are 0, sum is 0."""
        entries = [SelectionEntry(score=0.7, rank=0), SelectionEntry(score=0.3, rank=1)]
        result = allocate_count(entries, 0)
        allocations = [c for _, c in result]
        assert sum(allocations) == 0
        assert allocations == [0, 0]
