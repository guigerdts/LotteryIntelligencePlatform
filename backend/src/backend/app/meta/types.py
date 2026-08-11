"""Domain types for Meta Learning module.

Frozen dataclasses representing the core domain objects:
- ContextVector: engine context parameters (lottery_id, draws, cut, window, engine_type)
- WeightConfig: configurable scoring weights (META-001, META-019)
- RankingEntry: scored model within a ranking snapshot
- SelectionEntry: selected model within a selection snapshot
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextVector:
    """Immutable context resolving the engine snapshot parameters (META-003).

    All fields exist in the current schema. The context_hash is derived from
    these fields via SHA-256.
    """

    lottery_id: int
    draws_from: int
    draws_to: int
    cut: int | None
    window: int | None
    engine_type: str


@dataclass(frozen=True)
class WeightConfig:
    """Configurable scoring weights (META-001, META-019).

    Global defaults are hit_rate=0.3, average_matches=0.3, consistency_score=0.2,
    precision=0.1, recall=0.1. Per-lottery override via config_json replaces ALL
    defaults (no partial merge).
    """

    hit_rate: float = 0.3
    average_matches: float = 0.3
    consistency_score: float = 0.2
    precision: float = 0.1
    recall: float = 0.1

    def validate(self) -> None:
        """Reject zero-sum weights (META-001)."""
        total = self.hit_rate + self.average_matches + self.consistency_score + self.precision + self.recall
        if total == 0.0:
            raise ValueError("Weights must not sum to zero")


@dataclass(frozen=True)
class RankingEntry:
    """A scored model within a ranking snapshot (META-005)."""

    model_id: str
    engine_type: str
    score: float
    metrics: dict[str, float]


@dataclass(frozen=True)
class SelectionEntry:
    """A selected model within a selection snapshot (META-006)."""

    model_id: str
    engine_type: str
    rank: int
    score: float
