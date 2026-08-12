"""Sampling module — F5-weighted combination generation with resampling (GEN-005, GEN-006).

Generates deterministic lottery combinations by weighted random sampling from
F5 probability distributions × entry scores. Uses ``isolated_rng(seed)`` for
reproducibility. Invalid or duplicate combinations trigger resampling up to
``MAX_ATTEMPTS``; exhaustion raises ``GEN_SPACE_EXHAUSTED`` with zero combos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.app.generators.validation import validate_combination
from backend.app.probability.determinism import isolated_rng
from backend.app.services.errors import GenServiceError

MAX_ATTEMPTS: int = 1000
"""Hard limit for resampling loop (GEN-006)."""


class LotteryConfig(Protocol):
    """Minimal lottery configuration contract for sampling."""

    @property
    def numbers_to_select(self) -> int: ...
    @property
    def min_number(self) -> int: ...
    @property
    def max_number(self) -> int: ...
    @property
    def super_number_min(self) -> int: ...
    @property
    def super_number_max(self) -> int: ...


@dataclass(frozen=True)
class WeightedPool:
    """A number→probability distribution weighted by an entry score."""

    probabilities: dict[int, float]
    score: float


def sample_combinations(
    seed: int,
    pools: list[WeightedPool],
    count: int,
    lottery_config: LotteryConfig,
    max_attempts: int = MAX_ATTEMPTS,
) -> list[list[int]]:
    """Generate ``count`` unique valid lottery combinations (GEN-005, GEN-006).

    For each pool, weighted sampling uses ``rng.choices`` with weights derived
    from the pool's probability map × entry score. Invalid or duplicate combos
    trigger resampling. On ``max_attempts`` exhaustion → ``GEN_SPACE_EXHAUSTED``
    with zero combos persisted (GEN-013).

    Deterministic via ``isolated_rng(seed)`` — same seed always produces the
    same output (NFR-GEN-01).
    """
    rng = isolated_rng(seed)
    cfg = lottery_config
    generated: set[frozenset[int]] = set()
    results: list[list[int]] = []

    for pool in pools:
        # Build weighted pool: number → (probability × score)
        numbers = sorted(pool.probabilities.keys())
        weights = [pool.probabilities[n] * pool.score for n in numbers]

        needed = count - len(results)
        for _ in range(needed):
            for _attempt in range(max_attempts):
                combo = sorted(rng.choices(numbers, weights=weights, k=cfg.numbers_to_select))
                # Validate lottery rules
                if not validate_combination(combo, None, cfg):
                    continue
                # Duplicate rejection
                fs = frozenset(combo)
                if fs in generated:
                    continue
                generated.add(fs)
                results.append(combo)
                break
            else:
                raise GenServiceError(
                    GenServiceError.GEN_SPACE_EXHAUSTED,
                    "combination space exhausted after 1000 attempts",
                )

    return results
