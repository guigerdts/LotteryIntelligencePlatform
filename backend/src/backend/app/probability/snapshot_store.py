"""SnapshotStore: single prob_* I/O owner (design D-A3, PES-07).

Consolidates all read/write operations for ``prob_snapshots`` and ``prob_values``
in one module. Lifecycle enforcement (active→retired in one tx, failed header
never active/partial) lives here, not in the service layer (design §7).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.prob_snapshot import ProbSnapshot
from backend.app.models.prob_value import ProbValue


class SnapshotStore:
    """Prob_* read/write owner — lifecycle, bulk insert, ordered reads."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- reads ----------------------------------------------------------------

    def get_active(self, lottery_id: int, model_set: str) -> ProbSnapshot | None:
        """Return the current active snapshot for (lottery_id, model_set) or None."""
        stmt = (
            select(ProbSnapshot)
            .where(
                ProbSnapshot.lottery_id == lottery_id,
                ProbSnapshot.model_set == model_set,
                ProbSnapshot.status == "active",
            )
            .order_by(ProbSnapshot.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def find_by_fingerprint(
        self, lottery_id: int, model_set: str, fingerprint: str
    ) -> ProbSnapshot | None:
        """Return the active snapshot whose input_fingerprint matches, or None."""
        stmt = (
            select(ProbSnapshot)
            .where(
                ProbSnapshot.lottery_id == lottery_id,
                ProbSnapshot.model_set == model_set,
                ProbSnapshot.input_fingerprint == fingerprint,
                ProbSnapshot.status == "active",
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def next_version(self, lottery_id: int, model_set: str) -> str:
        """Return the next monotonic version string for (lottery_id, model_set)."""
        stmt = (
            select(ProbSnapshot.version)
            .where(
                ProbSnapshot.lottery_id == lottery_id,
                ProbSnapshot.model_set == model_set,
            )
            .order_by(ProbSnapshot.version.desc())
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
        prob_generator_version: str,
        checksum: str,
        input_fingerprint: str,
        status: str,
        is_locked: bool,
        draw_count: int,
        draws_from: int,
        draws_to: int,
    ) -> ProbSnapshot:
        """Create a new snapshot header row and return it."""
        snapshot = ProbSnapshot(
            lottery_id=lottery_id,
            model_set=model_set,
            version=version,
            prob_generator_version=prob_generator_version,
            checksum=checksum,
            input_fingerprint=input_fingerprint,
            status=status,
            is_locked=is_locked,
            draw_count=draw_count,
            draws_from=draws_from,
            draws_to=draws_to,
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def retire_old_active(
        self, lottery_id: int, model_set: str, *, keep_id: int
    ) -> None:
        """Retire all active snapshots except the one just created (PES-07)."""
        stmt = (
            update(ProbSnapshot)
            .where(
                ProbSnapshot.lottery_id == lottery_id,
                ProbSnapshot.model_set == model_set,
                ProbSnapshot.status == "active",
                ProbSnapshot.id != keep_id,
            )
            .values(status="retired", updated_at=datetime.now(UTC))
        )
        self._session.execute(stmt)

    def mark_failed(self, snapshot_id: int) -> None:
        """Mark a snapshot as failed (terminal, design §7)."""
        stmt = (
            update(ProbSnapshot)
            .where(ProbSnapshot.id == snapshot_id)
            .values(status="failed", is_locked=False, updated_at=datetime.now(UTC))
        )
        self._session.execute(stmt)

    def bulk_insert_values(
        self, snapshot_id: int, rows: Iterable[ProbValue]
    ) -> None:
        """Ordered bulk insert of ProbValue rows."""
        for row in rows:
            row.snapshot_id = snapshot_id
            self._session.add(row)
        self._session.flush()

    def values_for_snapshot(
        self,
        snapshot_id: int,
        *,
        model: str | None = None,
        subject: str | None = None,
        last: int = 0,
    ) -> list[ProbValue]:
        """Return persisted values ordered by (model_id, subject, draw_number)."""
        stmt = (
            select(ProbValue)
            .where(ProbValue.snapshot_id == snapshot_id)
            .order_by(ProbValue.model_id, ProbValue.subject, ProbValue.draw_number)
        )
        if model is not None:
            stmt = stmt.where(ProbValue.model_id == model)
        if subject is not None:
            stmt = stmt.where(ProbValue.subject == subject)
        if last > 0:
            stmt = stmt.limit(last)
        return list(self._session.execute(stmt).scalars().all())


__all__ = ["SnapshotStore"]
