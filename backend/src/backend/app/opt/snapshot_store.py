"""OptSnapshotStore: single opt_* I/O owner (design, OE-10, mirroring F7/F8 pattern).

Consolidates all read/write operations for ``opt_snapshots`` and ``opt_results``
in one module. Lifecycle enforcement (active→retired in one tx, failed header
never active) lives here, not in the service layer (design §7).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.opt_result import OptResult
from backend.app.models.opt_snapshot import OptSnapshot


class OptSnapshotStore:
    """opt_* read/write owner — lifecycle, bulk insert, ordered reads."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- reads ----------------------------------------------------------------

    def get_active(self, lottery_id: int, optimizer: str) -> OptSnapshot | None:
        """Return the current active snapshot for (lottery_id, optimizer) or None."""
        stmt = (
            select(OptSnapshot)
            .where(
                OptSnapshot.lottery_id == lottery_id,
                OptSnapshot.optimizer == optimizer,
                OptSnapshot.status == "active",
            )
            .order_by(OptSnapshot.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def find_by_fingerprint(
        self, lottery_id: int, optimizer: str, fingerprint: str
    ) -> OptSnapshot | None:
        """Return the active snapshot whose fingerprint matches, or None."""
        stmt = (
            select(OptSnapshot)
            .where(
                OptSnapshot.lottery_id == lottery_id,
                OptSnapshot.optimizer == optimizer,
                OptSnapshot.fingerprint == fingerprint,
                OptSnapshot.status == "active",
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def next_version(self, lottery_id: int, optimizer: str) -> str:
        """Return the next monotonic version string for (lottery_id, optimizer)."""
        stmt = (
            select(OptSnapshot.version)
            .where(
                OptSnapshot.lottery_id == lottery_id,
                OptSnapshot.optimizer == optimizer,
            )
            .order_by(OptSnapshot.version.desc())
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
        optimizer: str,
        model_set: str,
        objective_metric: str,
        objective_direction: str,
        algorithm_params: str,
        search_space: str,
        termination: str,
        termination_params: str | None,
        fingerprint: str,
        version: str,
        status: str,
        is_locked: bool,
        draw_count: int,
    ) -> OptSnapshot:
        """Create a new snapshot header row and return it."""
        snapshot = OptSnapshot(
            lottery_id=lottery_id,
            optimizer=optimizer,
            model_set=model_set,
            objective_metric=objective_metric,
            objective_direction=objective_direction,
            algorithm_params=algorithm_params,
            search_space=search_space,
            termination=termination,
            termination_params=termination_params,
            fingerprint=fingerprint,
            version=version,
            status=status,
            is_locked=is_locked,
            draw_count=draw_count,
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def retire_old_active(self, lottery_id: int, optimizer: str, *, keep_id: int) -> None:
        """Retire all active snapshots except the one just created (OE-10)."""
        stmt = (
            update(OptSnapshot)
            .where(
                OptSnapshot.lottery_id == lottery_id,
                OptSnapshot.optimizer == optimizer,
                OptSnapshot.status == "active",
                OptSnapshot.id != keep_id,
            )
            .values(status="retired", updated_at=datetime.now(UTC))
        )
        self._session.execute(stmt)

    def mark_failed(self, snapshot_id: int) -> None:
        """Mark a snapshot as failed (terminal, design §7)."""
        stmt = (
            update(OptSnapshot)
            .where(OptSnapshot.id == snapshot_id)
            .values(status="failed", is_locked=False, updated_at=datetime.now(UTC))
        )
        self._session.execute(stmt)

    def bulk_insert_results(self, snapshot_id: int, rows: Iterable[OptResult]) -> None:
        """Ordered bulk insert of OptResult rows."""
        for row in rows:
            row.snapshot_id = snapshot_id
            self._session.add(row)
        self._session.flush()

    def results_for_snapshot(
        self,
        snapshot_id: int,
        *,
        target_model: str | None = None,
    ) -> list[OptResult]:
        """Return persisted results ordered by (target_model)."""
        stmt = (
            select(OptResult)
            .where(OptResult.snapshot_id == snapshot_id)
            .order_by(OptResult.target_model)
        )
        if target_model is not None:
            stmt = stmt.where(OptResult.target_model == target_model)
        return list(self._session.execute(stmt).scalars().all())


__all__ = ["OptSnapshotStore"]
