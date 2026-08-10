"""OPT Provider Protocol contracts — the ONLY data seam the engine may import (OE-11).

The Optimization Engine defines, at its composition root, two read-only provider
interfaces. It imports ONLY these Protocols — never a concrete
``feature_engineering``/``models``/``repository`` implementation — so Evolution
behind the service never forces an engine change and there is no circular
dependency (OE-11). Adapters wrapping repositories live at the composition root,
out of this package.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DrawRow:
    """One draw on the official ``draw_number`` axis.

    ``numbers`` are the raw drawn main values already deterministically ordered
    by the provider. ``draw_number`` is the series axis — never ``draw_date``.
    """

    draw_number: int
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class FeatureRow:
    """One feature value from the active F4 snapshot.

    ``feature_id`` is the canonical feature identifier; ``draw_number`` links
    to the draw; ``value`` is the computed feature value.
    """

    feature_id: str
    draw_number: int
    value: float


class DrawHistoryProvider(Protocol):
    """Core-Domain read seam: deterministic, read-only draw iteration.

    ``iter_draws`` yields draws ordered by ``draw_number`` then internal
    insertion.
    """

    def iter_draws(
        self, lottery_id: int, *, after_draw_number: int | None = None
    ) -> Iterator[DrawRow]: ...


class FeatureSnapshotProvider(Protocol):
    """Feature-engine read seam: passive identity of an active feature snapshot.

    Returns feature value rows from the active F4 snapshot. A missing
    snapshot returns ``None`` — absence is never zero-guessed (OE-11).
    """

    def active_snapshot_id(self, lottery_id: int) -> int | None: ...

    def feature_rows(self, snapshot_id: int) -> Iterator[FeatureRow]: ...


__all__ = [
    "DrawHistoryProvider",
    "DrawRow",
    "FeatureRow",
    "FeatureSnapshotProvider",
]
