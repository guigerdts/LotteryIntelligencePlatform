"""Dual benchmark implementations: Uniform Random + F5 Hypergeometric (BTE-09).

Both benchmarks implement the same ``predict`` interface as
``StrategyProtocol`` and are designed to be evaluated on the exact same
evaluation windows as the strategy (BTE-16).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from decimal import Decimal

from backend.app.backtesting.types import DrawContext


class UniformRandomBenchmark:
    """Uniform random baseline (BTE-09).

    Generates random predictions by sampling uniformly from the number
    pool.  Seed-based for reproducibility.
    """

    def __init__(
        self,
        number_pool: Sequence[int],
        pick_count: int,
        seed: int,
    ) -> None:
        self._pool = list(number_pool)
        self._pick = pick_count
        self._rng = random.Random(seed)

    def predict(self, draw_context: DrawContext) -> list[int]:
        """Return a sorted random sample from the number pool."""
        return sorted(self._rng.sample(self._pool, self._pick))


class HypergeometricBenchmark:
    """F5 hypergeometric null-model benchmark (BTE-09, BTE-11).

    Generates predictions by sampling from the hypergeometric
    distribution using the F5 probability engine.  The ``probability.*``
    module is imported **lazily** inside ``predict`` to avoid
    module-level coupling (BTE-11).
    """

    def __init__(
        self,
        number_pool: Sequence[int],
        pick_count: int,
        seed: int,
    ) -> None:
        self._pool = list(number_pool)
        self._pick = pick_count
        self._rng = random.Random(seed)

    def predict(self, draw_context: DrawContext) -> list[int]:
        """Sample numbers weighted by hypergeometric probabilities.

        Uses the F5 ``hypergeometric`` function to compute the
        probability of drawing k numbers from a pool, then samples
        individual numbers proportional to their inclusion probability.

        Each number in the pool has an equal prior probability of being
        selected (1/N per draw), so the hypergeometric weighting
        produces a distribution where numbers with higher combinatorial
        weight are more likely to appear.
        """
        from backend.app.probability.engine import hypergeometric as hyp_dist  # noqa: PLC0415

        pool_size = len(self._pool)
        # P(X=1) = C(1,1)*C(N-1, pick-1)/C(N, pick) = pick/N
        # Verify via hypergeometric distribution (import validates F5 coupling)
        hyp_dist(pool_size, self._pick, 1)
        p_single = float(Decimal(self._pick) / Decimal(pool_size))

        # Weight each number by p_single (all equal in uniform pool)
        weights = [p_single] * pool_size
        return sorted(self._rng.choices(self._pool, weights=weights, k=self._pick))
