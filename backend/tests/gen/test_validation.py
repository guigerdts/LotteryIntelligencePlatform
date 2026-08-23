"""Tests for generator validation — lottery rules check (GEN-006).

Spec refs: GEN-006 (lottery rules), GEN-018 (no filters MVP).
Design refs: Module Structure (validation.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.app.generators.validation import validate_combination


@dataclass(frozen=True)
class LotteryConfig:
    """Minimal lottery configuration for validation."""

    numbers_to_select: int
    min_number: int
    max_number: int
    super_number_min: int
    super_number_max: int


class TestValidateCombination:
    """validate_combination() — GEN-006 lottery rules."""

    @pytest.fixture
    def cfg(self) -> LotteryConfig:
        return LotteryConfig(
            numbers_to_select=6,
            min_number=1,
            max_number=49,
            super_number_min=1,
            super_number_max=9,
        )

    def test_valid_combo(self, cfg: LotteryConfig) -> None:
        """Valid combination → True."""
        assert validate_combination([1, 15, 22, 33, 41, 49], 7, cfg) is True

    def test_none_super_number_returns_false(self, cfg: LotteryConfig) -> None:
        """Missing Superbalota → False (D5 legality tightening, R1)."""
        assert validate_combination([1, 15, 22, 33, 41, 49], None, cfg) is False

    def test_unsorted_returns_false(self, cfg: LotteryConfig) -> None:
        """Unsorted numbers → False."""
        assert validate_combination([49, 15, 22, 33, 41, 1], 7, cfg) is False

    def test_out_of_range_returns_false(self, cfg: LotteryConfig) -> None:
        """Number out of [min, max] → False."""
        assert validate_combination([0, 15, 22, 33, 41, 49], 7, cfg) is False
        assert validate_combination([1, 15, 22, 33, 41, 50], 7, cfg) is False

    def test_duplicate_returns_false(self, cfg: LotteryConfig) -> None:
        """Duplicate numbers → False."""
        assert validate_combination([1, 1, 22, 33, 41, 49], 7, cfg) is False

    def test_wrong_count_returns_false(self, cfg: LotteryConfig) -> None:
        """Wrong number count → False."""
        assert validate_combination([1, 15, 22, 33, 41], 7, cfg) is False
        assert validate_combination([1, 15, 22, 33, 41, 49, 7], 7, cfg) is False

    def test_super_number_out_of_range_returns_false(self, cfg: LotteryConfig) -> None:
        """Super number out of [super_number_min, super_number_max] → False."""
        assert validate_combination([1, 15, 22, 33, 41, 49], 0, cfg) is False
        assert validate_combination([1, 15, 22, 33, 41, 49], 10, cfg) is False

    def test_super_number_in_range(self, cfg: LotteryConfig) -> None:
        """Super number within valid range → True."""
        assert validate_combination([1, 15, 22, 33, 41, 49], 1, cfg) is True
        assert validate_combination([1, 15, 22, 33, 41, 49], 9, cfg) is True
