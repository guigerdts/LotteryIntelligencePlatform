"""Provider Protocol contracts and data carries — the ONLY data seam (PES-06).

The Probability Engine defines, at its composition root, three read-only
provider interfaces plus the pure carries they pass. The engine imports ONLY
these Protocols: it never touches a concrete ``statistics``/``feature_engineering``/
``models``/``repositories`` implementation (PES-06, design §Design). Missing
data surfaces as ``None``/absent — it is never guessed (STE-09 parity).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DrawRow:
    """One draw on the official ``draw_number`` axis (PES-03).

    ``numbers`` are the raw drawn main values already deterministically ordered
    by the provider. ``draw_number`` is the series axis — never ``draw_date``.
    """

    draw_number: int
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class LotteryRules:
    """Immutable lottery rule set needed by the probability models (PES-10)."""

    min_number: int
    max_number: int
    numbers_to_select: int

    @property
    def pool_size(self) -> int:
        """N = max - min + 1 (PM-01 hypergeometric population)."""
        return self.max_number - self.min_number + 1


@dataclass(frozen=True)
class StatsSnapshotRef:
    """Read-only identity of an active statistics snapshot (STE-10, no precompute)."""

    id: int
    checksum: str
    generator_version: str
    draws_from: int
    draws_to: int


@dataclass(frozen=True)
class FeatureSnapshotRef:
    """Read-only identity of an active feature snapshot (read-only seam)."""

    id: int
    checksum: str
    feature_engine_version: str


class DrawReader(Protocol):
    """Core-Domain read seam: deterministic, read-only draw iteration.

    ``iter_draws`` yields draws ordered by ``draw_number`` then internal
    insertion (``ORDER BY draw.draw_number, draw_numbers.id``, design §3) and
    ``lottery_rules`` returns the immutable rule record for a lottery.
    """

    def iter_draws(
        self, lottery_id: int, *, after_draw_number: int | None = None
    ) -> Iterator[DrawRow]: ...

    def lottery_rules(self, lottery_id: int) -> LotteryRules: ...


class StatSnapshotReader(Protocol):
    """Statistics read seam: passive, active-snapshot-only, never precomputes.

    Resolves only the active snapshot identity and its stored frequencies —
    never a recompute. A missing snapshot returns ``None`` and stats-sourced
    models are skipped, never guessed.
    """

    def active(self, lottery_id: int, metric_set: str = "core") -> StatsSnapshotRef | None: ...

    def frequencies(
        self, snapshot_id: int, metric_set: str = "core"
    ) -> Mapping[int, int]: ...


class FeatureSnapshotReader(Protocol):
    """Feature-engine read seam: passive identity of an active feature snapshot."""

    def active(
        self, lottery_id: int, feature_set: str = "core"
    ) -> FeatureSnapshotRef | None: ...


__all__ = [
    "DrawReader",
    "DrawRow",
    "FeatureSnapshotReader",
    "FeatureSnapshotRef",
    "LotteryRules",
    "StatSnapshotReader",
    "StatsSnapshotRef",
]