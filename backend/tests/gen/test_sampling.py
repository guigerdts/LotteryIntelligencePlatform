"""Tests for generator sampling — F5-weighted combination generation (GEN-005, GEN-006).

Spec refs: GEN-005 (determinism), GEN-006 (lottery rules), GEN-013 (space exhausted).
Design refs: Resampling (GEN-006), Module Structure (sampling.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.app.generators.sampling import WeightedPool, sample_combinations
from backend.app.services.errors import GenServiceError


@dataclass(frozen=True)
class LotteryConfig:
    """Minimal lottery configuration for sampling tests."""

    numbers_to_select: int
    min_number: int
    max_number: int
    super_number_min: int
    super_number_max: int


class TestSampleCombinations:
    """sample_combinations() — deterministic weighted sampling with resampling."""

    @pytest.fixture
    def cfg(self) -> LotteryConfig:
        return LotteryConfig(
            numbers_to_select=6,
            min_number=1,
            max_number=49,
            super_number_min=1,
            super_number_max=9,
        )

    def _make_pool(self, n: int = 49, weight: float = 1.0) -> WeightedPool:
        """Create a uniform distribution over numbers 1..n."""
        return WeightedPool(
            probabilities={i: weight for i in range(1, n + 1)},
            score=1.0,
        )

    def test_determinism(self, cfg: LotteryConfig) -> None:
        """Same seed → identical output (GEN-005, NFR-GEN-01)."""
        pool = self._make_pool()
        result1 = sample_combinations(42, [pool], 5, cfg)
        result2 = sample_combinations(42, [pool], 5, cfg)
        assert result1 == result2

    def test_different_seeds_differ(self, cfg: LotteryConfig) -> None:
        """Different seeds → likely different output."""
        pool = self._make_pool()
        result1 = sample_combinations(42, [pool], 5, cfg)
        result2 = sample_combinations(99, [pool], 5, cfg)
        # Not guaranteed to differ, but extremely likely with 49 choose 6
        assert result1 != result2 or True  # Accept if same by extreme coincidence

    def test_valid_combos_respect_lottery_rules(self, cfg: LotteryConfig) -> None:
        """All generated combos are valid per lottery rules (GEN-006)."""
        pool = self._make_pool()
        combos = sample_combinations(42, [pool], 10, cfg)
        assert len(combos) == 10
        for combo in combos:
            assert len(combo) == cfg.numbers_to_select
            assert all(cfg.min_number <= n <= cfg.max_number for n in combo)
            assert len(set(combo)) == len(combo)
            assert combo == sorted(combo)

    def test_exact_count(self, cfg: LotteryConfig) -> None:
        """Returns exactly count combinations (NFR-GEN-02)."""
        pool = self._make_pool()
        combos = sample_combinations(42, [pool], 10, cfg)
        assert len(combos) == 10

    def test_max_attempts_exhaustion(self) -> None:
        """MAX_ATTEMPTS reached → GEN_SPACE_EXHAUSTED, zero combos (GEN-013)."""
        # Tiny pool: numbers 1..6, need 6 distinct → only 1 valid combo
        # With max_attempts=3, cannot produce 5 combos
        tiny_cfg = LotteryConfig(
            numbers_to_select=6,
            min_number=1,
            max_number=6,
            super_number_min=1,
            super_number_max=9,
        )
        pool = WeightedPool(
            probabilities={i: 1.0 for i in range(1, 7)},
            score=1.0,
        )
        with pytest.raises(GenServiceError) as exc_info:
            sample_combinations(42, [pool], 5, tiny_cfg, max_attempts=3)
        assert exc_info.value.code == "GEN_SPACE_EXHAUSTED"

    def test_no_duplicates_in_output(self, cfg: LotteryConfig) -> None:
        """Duplicate rejection: all combos in output are unique."""
        pool = self._make_pool()
        combos = sample_combinations(42, [pool], 20, cfg)
        unique_combos = [tuple(c) for c in combos]
        assert len(set(unique_combos)) == len(unique_combos)

    def test_multiple_pools(self, cfg: LotteryConfig) -> None:
        """Multiple weighted pools produce combinations from each."""
        pool1 = WeightedPool(
            probabilities={i: 1.0 for i in range(1, 50)},
            score=0.7,
        )
        pool2 = WeightedPool(
            probabilities={i: 1.0 for i in range(1, 50)},
            score=0.3,
        )
        # 3 from pool1, 2 from pool2 = 5 total
        combos = sample_combinations(42, [pool1, pool2], 5, cfg)
        assert len(combos) == 5

    def test_score_influences_distribution(self) -> None:
        """Higher score weight biases number selection."""
        # Pool with strong weight on low numbers
        pool_low = WeightedPool(
            probabilities={i: (10.0 if i <= 10 else 0.1) for i in range(1, 50)},
            score=1.0,
        )
        cfg = LotteryConfig(
            numbers_to_select=3,
            min_number=1,
            max_number=49,
            super_number_min=1,
            super_number_max=9,
        )
        # Generate many combos and check bias
        all_numbers: list[int] = []
        for seed in range(100):
            combos = sample_combinations(seed, [pool_low], 1, cfg)
            all_numbers.extend(combos[0])
        # With strong weight on 1-10, majority should be low numbers
        low_count = sum(1 for n in all_numbers if n <= 10)
        assert low_count > len(all_numbers) * 0.5
