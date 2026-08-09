"""MlSnapshotStore: single ml_* I/O owner (design, MLE-08, mirroring F5 pattern).

Consolidates all read/write operations for ``ml_snapshots`` and ``ml_metrics``
in one module. Lifecycle enforcement (active→retired in one tx, failed header
never active) lives here, not in the service layer (design §7).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.ml_metric import MlMetric
from backend.app.models.ml_snapshot import MlSnapshot


class MlSnapshotStore:
    """ml_* read/write owner — lifecycle, bulk insert, ordered reads."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- reads ----------------------------------------------------------------

    def get_active(self, lottery_id: int, model_set: str) -> MlSnapshot | None:
        """Return the current active snapshot for (lottery_id, model_set) or None."""
        stmt = (
            select(MlSnapshot)
            .where(
                MlSnapshot.lottery_id == lottery_id,
                MlSnapshot.model_set == model_set,
                MlSnapshot.status == "active",
            )
            .order_by(MlSnapshot.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def find_by_fingerprint(
        self, lottery_id: int, model_set: str, fingerprint: str
    ) -> MlSnapshot | None:
        """Return the active snapshot whose input_fingerprint matches, or None."""
        stmt = (
            select(MlSnapshot)
            .where(
                MlSnapshot.lottery_id == lottery_id,
                MlSnapshot.model_set == model_set,
                MlSnapshot.input_fingerprint == fingerprint,
                MlSnapshot.status == "active",
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def next_version(self, lottery_id: int, model_set: str) -> str:
        """Return the next monotonic version string for (lottery_id, model_set)."""
        stmt = (
            select(MlSnapshot.version)
            .where(
                MlSnapshot.lottery_id == lottery_id,
                MlSnapshot.model_set == model_set,
            )
            .order_by(MlSnapshot.version.desc())
            .limit(1)
        )
        last = self._session.execute(stmt).scalar_one_or_none()
        if last is None:
            return "1"
        return str(int(last) + 1)

    # --- writes ---------------------------------------------------------------

    def create_snapshot(
        self,
        *,
        lottery_id: int,
        model_set: str,
        version: str,
        ml_generator_version: str,
        checksum: str,
        input_fingerprint: str,
        cut: int,
        status: str,
        is_locked: bool,
        draw_count: int,
        draws_from: int,
        draws_to: int,
    ) -> MlSnapshot:
        """Create a new snapshot header row and return it."""
        snapshot = MlSnapshot(
            lottery_id=lottery_id,
            model_set=model_set,
            version=version,
            ml_generator_version=ml_generator_version,
            checksum=checksum,
            input_fingerprint=input_fingerprint,
            cut=cut,
            status=status,
            is_locked=is_locked,
            draw_count=draw_count,
            draws_from=draws_from,
            draws_to=draws_to,
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def retire_old_active(self, lottery_id: int, model_set: str, *, keep_id: int) -> None:
        """Retire all active snapshots except the one just created (PES-07)."""
        stmt = (
            update(MlSnapshot)
            .where(
                MlSnapshot.lottery_id == lottery_id,
                MlSnapshot.model_set == model_set,
                MlSnapshot.status == "active",
                MlSnapshot.id != keep_id,
            )
            .values(status="retired", updated_at=datetime.now(UTC))
        )
        self._session.execute(stmt)

    def mark_failed(self, snapshot_id: int) -> None:
        """Mark a snapshot as failed (terminal, design §7)."""
        stmt = (
            update(MlSnapshot)
            .where(MlSnapshot.id == snapshot_id)
            .values(status="failed", is_locked=False, updated_at=datetime.now(UTC))
        )
        self._session.execute(stmt)

    def bulk_insert_metrics(self, snapshot_id: int, rows: Iterable[MlMetric]) -> None:
        """Ordered bulk insert of MlMetric rows."""
        for row in rows:
            row.snapshot_id = snapshot_id
            self._session.add(row)
        self._session.flush()

    def metrics_for_snapshot(
        self,
        snapshot_id: int,
        *,
        model_id: str | None = None,
        number: int | None = None,
    ) -> list[MlMetric]:
        """Return persisted metrics ordered by (model_id, number, metric_name)."""
        stmt = (
            select(MlMetric)
            .where(MlMetric.snapshot_id == snapshot_id)
            .order_by(MlMetric.model_id, MlMetric.number, MlMetric.metric_name)
        )
        if model_id is not None:
            stmt = stmt.where(MlMetric.model_id == model_id)
        if number is not None:
            stmt = stmt.where(MlMetric.number == number)
        return list(self._session.execute(stmt).scalars().all())


__all__ = ["MlSnapshotStore"]
