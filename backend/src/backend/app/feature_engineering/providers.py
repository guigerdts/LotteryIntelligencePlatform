"""Provider Protocol contracts — the ONLY data seam the engine may import (FES-06).

The Feature Engine defines, at its composition root, three read-only provider
interfaces. It imports ONLY these Protocols — never a concrete
``statistics``/``models``/``repository`` implementation — so Evolution behind the
service never forces an engine change and there is no circular dependency
(design §4, FES-06). Adapters wrapping ``draw_repository`` / ``StatPayloadRepository``
live at the composition root, out of this package.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Protocol

from backend.app.feature_engineering.context import DrawRow, LotteryRules


class DrawProvider(Protocol):
    """Core-Domain read seam: deterministic, batched, keyset, read-only.

    ``iter_draws`` yields draws ordered by ``draw_number`` then internal insertion
    (``ORDER BY draw.draw_number, draw_numbers.id``, design §9) — never physical scan
    order. ``after_draw_number`` provides the incremental ``delta`` window.
    """

    def iter_draws(
        self,
        lottery_id: int,
        *,
        after_draw_number: int | None = None,
    ) -> Iterator[DrawRow]: ...

    def lottery_rules(self, lottery_id: int) -> LotteryRules: ...


class StatsSnapshotRef(Protocol):
    """Read-only identity of an active statistics snapshot (STE-10, no precompute)."""

    @property
    def id(self) -> int: ...

    @property
    def checksum(self) -> str: ...

    @property
    def generator_version(self) -> str: ...

    @property
    def draws_from(self) -> int: ...

    @property
    def draws_to(self) -> int: ...


class StatisticsProvider(Protocol):
    """Statistics read seam: passive, active-snapshot-only, never precomputes.

    Resolves only the active snapshot identity and its scalars. The engine NEVER asks
    this provider to compute anything (STE-10) — a missing snapshot returns ``None``
    and stats-sourced features are ``skipped``, never guessed.
    """

    def active_snapshot(
        self, lottery_id: int, metric_set: str = "core"
    ) -> StatsSnapshotRef | None: ...

    def scalars(self, snapshot_id: int) -> Mapping[str, Decimal]: ...


class DatasetHeaderRef(Protocol):
    """Identity of an active dataset (Fase 2 seam, declared not exercised in slice 1)."""

    @property
    def id(self) -> int: ...

    @property
    def checksum(self) -> str: ...


class DatasetProvider(Protocol):
    """Dataset seam (Fase 2): immutable, checksummed datasets as optional draw sources."""

    def active_dataset(self, lottery_id: int) -> DatasetHeaderRef | None: ...
