"""Sampling module — F5-weighted combination generation with resampling (GEN-005, GEN-006).

Generates deterministic lottery ``(combination, super_balota)`` pairs by weighted
random sampling from F5 probability distributions × entry scores. Uses
``isolated_rng(seed)`` for reproducibility; the Superbalota is drawn from the SAME
stream once per accepted combination (R2/D1), so one seed reproduces the entire
ticket including SB. Invalid or duplicate combinations trigger resampling up to
``MAX_ATTEMPTS``; exhaustion raises ``GEN_SPACE_EXHAUSTED`` with zero combos.
Legality (numbers + SB) is gated pre-persist inside the loop (R1/D5).
"""

from __future__ import annotations

from collections.abc import Mapping
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
    sb_marginal: Mapping[int, float] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> list[tuple[list[int], int]]:
    """Generate ``count`` unique valid ``(combination, super_balota)`` pairs.

    For each pool, weighted sampling uses ``rng.choices`` with weights derived
    from the pool's probability map × entry score. Invalid or duplicate combos
    trigger resampling. On each ACCEPTED combination the Superbalota is drawn
    ONCE from the same ``isolated_rng(seed)`` stream over ``sb_marginal``
    (D1: post-acceptance draw keeps stream consumption independent of rejection
    counts), and the full pair is legality-gated pre-append (D5/R1).

    ``sb_marginal`` maps candidate SB values to relative weights; when ``None``
    a uniform distribution over the configured SB range is used. On
    ``max_attempts`` exhaustion → ``GEN_SPACE_EXHAUSTED`` with zero combos
    persisted (GEN-013).

    Deterministic via ``isolated_rng(seed)`` — same seed always produces the
    same output including Superbalotas (NFR-GEN-01, R2).
    """
    rng = isolated_rng(seed)
    cfg = lottery_config
    if sb_marginal is None:
        span = cfg.super_number_max - cfg.super_number_min + 1
        sb_marginal = {n: 1.0 / span for n in range(cfg.super_number_min, cfg.super_number_max + 1)}
    sb_numbers = sorted(sb_marginal)
    sb_weights = [float(sb_marginal[n]) for n in sb_numbers]

    generated: set[frozenset[int]] = set()
    results: list[tuple[list[int], int]] = []

    for pool in pools:
        # Build weighted pool: number → (probability × score)
        numbers = sorted(pool.probabilities.keys())
        weights = [pool.probabilities[n] * pool.score for n in numbers]

        needed = count - len(results)
        for _ in range(needed):
            for _attempt in range(max_attempts):
                combo = sorted(rng.choices(numbers, weights=weights, k=cfg.numbers_to_select))
                # Validate lottery rules (numbers shape only — SB not drawn yet)
                if _numbers_invalid(combo, cfg):
                    continue
                # Duplicate rejection
                fs = frozenset(combo)
                if fs in generated:
                    continue
                generated.add(fs)
                # D1: draw the Superbalota ONCE per accepted combo, same stream.
                sb = rng.choices(sb_numbers, weights=sb_weights, k=1)[0]
                # D5/R1: legality gate before the pair can be persisted upstream.
                if not validate_combination(combo, sb, cfg):
                    raise GenServiceError(
                        GenServiceError.GEN_INVALID_SUPER_NUMBER,
                        f"sampled super number {sb} outside "
                        f"[{cfg.super_number_min}, {cfg.super_number_max}]",
                    )
                results.append((combo, sb))
                break
            else:
                raise GenServiceError(
                    GenServiceError.GEN_SPACE_EXHAUSTED,
                    "combination space exhausted after 1000 attempts",
                )

    return results


def _numbers_invalid(combo: list[int], cfg: LotteryConfig) -> bool:
    """Return True when the number part alone violates lottery rules."""
    return (
        len(combo) != cfg.numbers_to_select
        or len(set(combo)) != len(combo)
        or any(n < cfg.min_number or n > cfg.max_number for n in combo)
        or combo != sorted(combo)
    )


__all__ = ["MAX_ATTEMPTS", "WeightedPool", "sample_combinations"]
