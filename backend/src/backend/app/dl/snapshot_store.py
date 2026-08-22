"""DlSnapshotStore: single dl_* I/O owner (design DlSnapshotStore contract, ADR-1/ADR-2).

Consolidates every read/write for ``dl_snapshots``, ``dl_metrics`` and ``dl_weights``
in one module, mirroring ``MlSnapshotStore`` method-for-method. Flush-only (ADR-1):
every write ends in ``flush()`` and the store NEVER calls ``commit()``/``rollback()``
— the caller owns the single transaction boundary that guarantees exactly-one-active
per ``(lottery_id, model_set)`` mid-flight. Weight retirement deletes the superseded
active's ``dl_weights`` rows inside the same transaction (ADR-2/DLE-12), so callers
cannot forget the delete half of retirement. Terminal failure persistence uses the
recreate pattern: after a rollback discards the placeholder INSERT an UPDATE-by-id
would match zero rows, so ``mark_failed`` re-inserts a fresh terminal header instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.app.models.dl_metric import DlMetric
from backend.app.models.dl_snapshot import DlSnapshot
from backend.app.models.dl_weight import DlWeight

# 16 MiB ceiling mirrored from ck_dl_weights_max_size (models/dl_weight.py); enforced
# here BEFORE staging so oversized blobs never enter the session (DDL is the backstop).
_MAX_WEIGHTS_SIZE = 16_777_216


class DlSnapshotStore:
    """dl_* read/write owner — lifecycle, bulk inserts, weight retirement."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- reads ----------------------------------------------------------------

    def get_active(self, lottery_id: int, model_set: str) -> DlSnapshot | None:
        """Return the newest active snapshot for (lottery_id, model_set) or None."""
        stmt = (
            select(DlSnapshot)
            .where(
                DlSnapshot.lottery_id == lottery_id,
                DlSnapshot.model_set == model_set,
                DlSnapshot.status == "active",
            )
            .order_by(DlSnapshot.version.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def find_by_fingerprint(
        self, lottery_id: int, model_set: str, fingerprint: str
    ) -> DlSnapshot | None:
        """Return the active snapshot whose input_fingerprint matches, or None."""
        stmt = (
            select(DlSnapshot)
            .where(
                DlSnapshot.lottery_id == lottery_id,
                DlSnapshot.model_set == model_set,
                DlSnapshot.input_fingerprint == fingerprint,
                DlSnapshot.status == "active",
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def next_version(self, lottery_id: int, model_set: str) -> str:
        """Return the next monotonic version string for (lottery_id, model_set)."""
        stmt = (
            select(DlSnapshot.version)
            .where(
                DlSnapshot.lottery_id == lottery_id,
                DlSnapshot.model_set == model_set,
            )
            .order_by(DlSnapshot.version.desc())
            .limit(1)
        )
        last = self._session.execute(stmt).scalar_one_or_none()
        if last is None:
            return "1"
        return str(int(last) + 1)

    def metrics_for_snapshot(
        self,
        snapshot_id: int,
        *,
        model_id: str | None = None,
    ) -> list[DlMetric]:
        """Return persisted metrics ordered by (model_id, metric_name), optionally filtered."""
        stmt = (
            select(DlMetric)
            .where(DlMetric.snapshot_id == snapshot_id)
            .order_by(DlMetric.model_id, DlMetric.metric_name)
        )
        if model_id is not None:
            stmt = stmt.where(DlMetric.model_id == model_id)
        return list(self._session.execute(stmt).scalars().all())

    # --- writes (flush-only; ADR-1: caller owns commit) ------------------------

    def create_snapshot(
        self,
        *,
        lottery_id: int,
        model_set: str,
        version: str,
        dl_generator_version: str,
        checksum: str = "",
        input_fingerprint: str = "",
        cut: int = 0,
        window: int = 0,
        status: str = "active",
        is_locked: bool = True,
        draw_count: int,
        draws_from: int,
        draws_to: int,
    ) -> DlSnapshot:
        """Create a snapshot header row and return it (flush assigns the id)."""
        snapshot = DlSnapshot(
            lottery_id=lottery_id,
            model_set=model_set,
            version=version,
            dl_generator_version=dl_generator_version,
            checksum=checksum,
            input_fingerprint=input_fingerprint,
            cut=cut,
            window=window,
            status=status,
            is_locked=is_locked,
            draw_count=draw_count,
            draws_from=draws_from,
            draws_to=draws_to,
        )
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def bulk_insert_metrics(self, snapshot_id: int, rows: Iterable[DlMetric]) -> None:
        """Ordered bulk insert of DlMetric rows (exact Decimal values only)."""
        for row in rows:
            row.snapshot_id = snapshot_id
            self._session.add(row)
        self._session.flush()

    def insert_weights(self, rows: Iterable[DlWeight]) -> None:
        """Stage DL weight blobs behind the pre-INSERT size gate (DLE-09)."""
        for row in rows:
            if len(row.weights_blob) > _MAX_WEIGHTS_SIZE:
                msg = (
                    f"weights_blob for {row.model_id!r} is {len(row.weights_blob)} bytes;"
                    f" maximum allowed is {_MAX_WEIGHTS_SIZE}"
                )
                raise ValueError(msg)
            self._session.add(row)
        self._session.flush()

    def delete_weights_for(self, snapshot_ids: Iterable[int]) -> None:
        """Delete every dl_weights row belonging to the given snapshot ids."""
        ids = list(snapshot_ids)
        if not ids:
            return
        self._session.execute(delete(DlWeight).where(DlWeight.snapshot_id.in_(ids)))
        self._session.flush()

    def retire_old_active(self, lottery_id: int, model_set: str, *, keep_id: int) -> None:
        """Retire every other active AND delete its weight rows in-tx (ADR-2, DLE-12)."""
        ids = list(
            self._session.execute(
                select(DlSnapshot.id).where(
                    DlSnapshot.lottery_id == lottery_id,
                    DlSnapshot.model_set == model_set,
                    DlSnapshot.status == "active",
                    DlSnapshot.id != keep_id,
                )
            ).scalars()
        )
        if not ids:
            return
        self._session.execute(
            update(DlSnapshot)
            .where(DlSnapshot.id.in_(ids))
            .values(status="retired", updated_at=datetime.now(UTC))
        )
        self.delete_weights_for(ids)

    def mark_failed(
        self,
        *,
        lottery_id: int,
        model_set: str,
        version: str,
        dl_generator_version: str,
        cut: int,
        window: int,
        draw_count: int,
        draws_from: int,
        draws_to: int,
    ) -> DlSnapshot:
        """Re-insert a terminal failed header AFTER the rollback (recreate gotcha).

        The rolled-back placeholder's identity no longer exists, so an UPDATE-style
        mark would persist nothing; reusing the same version string is safe because
        the rollback freed the UNIQUE ``(lottery_id, model_set, version)`` slot.
        """
        return self.create_snapshot(
            lottery_id=lottery_id,
            model_set=model_set,
            version=version,
            dl_generator_version=dl_generator_version,
            checksum="",
            input_fingerprint="",
            cut=cut,
            window=window,
            status="failed",
            is_locked=False,
            draw_count=draw_count,
            draws_from=draws_from,
            draws_to=draws_to,
        )


__all__ = ["DlSnapshotStore"]
