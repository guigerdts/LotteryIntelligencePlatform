"""StatSnapshot repository: header CRUD + active/latest resolution + versioning (design §2).

Persistence-only primitives over the DI session; the immutable-bump and fail/retire
policy are service-owned (design §7). ``create``/``get``/``update`` come from the
generic base. This repository owns the queries the service needs for the
idempotency/preview and incremental/full paths: resolving the current ``active``
row, the newest ``version`` for a scope, finding an idempotent match by checksum +
generator_version, and flipping superseded snapshots to ``retired`` in the same
transaction that writes a new version.

Repositories never ``commit``; the service owns the single atomic transaction
(design §3).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.stat_snapshot import StatSnapshot
from backend.app.repositories.base_repository import BaseRepository


class StatSnapshotRepository(BaseRepository[StatSnapshot]):
    """CRUD + active/latest/idempotency/retire primitives over one DI session."""

    model = StatSnapshot

    def get_active(self, lottery_id: int, metric_set: str) -> StatSnapshot | None:
        """Return the single ``status='active'`` snapshot for a (lottery, metric_set).

        Exactly one active row per scope is enforced by the service (design §2);
        this geometric lookup reads it for the incremental/preview and idempotency
        paths.
        """
        return self._session.scalar(
            select(StatSnapshot).where(
                StatSnapshot.lottery_id == lottery_id,
                StatSnapshot.metric_set == metric_set,
                StatSnapshot.status == "active",
            )
        )

    def latest(self, lottery_id: int, metric_set: str) -> StatSnapshot | None:
        """Return the highest ``version`` snapshot (any status) or ``None``.

        Supplies the monotonic version source: the next version is derived from
        the newest existing row regardless of status, so a failed generation that
        bumps the counter is never reused (design §3 resume = new snapshot).
        """
        return self._session.scalar(
            select(StatSnapshot)
            .where(
                StatSnapshot.lottery_id == lottery_id,
                StatSnapshot.metric_set == metric_set,
            )
            .order_by(StatSnapshot.version.desc())
            .limit(1)
        )

    def find_by_checksum_version(
        self,
        lottery_id: int,
        metric_set: str,
        checksum: str,
        generator_version: str,
    ) -> StatSnapshot | None:
        """Idempotency lookup: an ``active`` snapshot that already encodes this exact result.

        Matches on checksum + generator_version (+ the fixed lottery/metric_set
        scope via WHERE) so a repro that would recreate an identical snapshot
        returns the existing row without writing a duplicate version (design §5).
        """
        return self._session.scalar(
            select(StatSnapshot).where(
                StatSnapshot.lottery_id == lottery_id,
                StatSnapshot.metric_set == metric_set,
                StatSnapshot.status == "active",
                StatSnapshot.checksum == checksum,
                StatSnapshot.generator_version == generator_version,
            )
        )

    def next_version(self, lottery_id: int, metric_set: str) -> str:
        """Return the next monotonic ``version`` string for a scope (design §2).

        ``latest`` provides the newest existing numeric version (any status); the
        next version is ``latest + 1``, or ``"1"`` when no row exists. Version is
        immutable per (lottery, metric_set) via UNIQUE — a retry always bumps.
        """
        latest = self.latest(lottery_id, metric_set)
        if latest is None:
            return "1"
        return str(int(latest.version) + 1)

    def retire_old_active(self, lottery_id: int, metric_set: str, keep_id: int) -> int:
        """Flip every other ``active`` row to ``retired`` in the same tx (design §7).

        Exactly one ``active`` per (lottery, metric_set) is preserved: the newly
        created row (``keep_id``) stays active while prior active rows are
        retired. Returns the number of rows retired. Called inside the creating
        transaction so replacement is atomic — the old immutable snapshot is never
        ``UPDATE``d in place beyond its status, and its payload rows are untouched.
        """
        now = datetime.now(UTC)
        result = self._session.execute(
            update(StatSnapshot)
            .where(
                StatSnapshot.lottery_id == lottery_id,
                StatSnapshot.metric_set == metric_set,
                StatSnapshot.status == "active",
                StatSnapshot.id != keep_id,
            )
            .values(status="retired", updated_at=now)
        )
        return int(result.rowcount if result.rowcount is not None else 0)

    def create_snapshot(
        self,
        *,
        lottery_id: int,
        metric_set: str,
        version: str,
        generator_version: str,
        engine_version: str,
        checksum: str,
        status: str,
        is_locked: bool,
        draw_count: int,
        draws_from: int,
        draws_to: int,
    ) -> StatSnapshot:
        """Insert one snapshot header via the generic ``create`` (flush surfaces UNIQUE)."""
        return self.create(
            {
                "lottery_id": lottery_id,
                "metric_set": metric_set,
                "version": version,
                "generator_version": generator_version,
                "engine_version": engine_version,
                "checksum": checksum,
                "status": status,
                "is_locked": is_locked,
                "draw_count": draw_count,
                "draws_from": draws_from,
                "draws_to": draws_to,
                "parser_version": None,
            }
        )

    @staticmethod
    def session_for(db_session: Session) -> StatSnapshotRepository:
        """Return a repository bound to ``db_session`` (DI convenience)."""
        return StatSnapshotRepository(db_session)
