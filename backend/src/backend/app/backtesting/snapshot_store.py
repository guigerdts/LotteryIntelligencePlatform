"""BtSnapshotStore — bt_* I/O owner (BTE-10).

Handles all persistence for ``bt_snapshots`` and ``bt_results`` with
atomic lifecycle transitions, fingerprint-based idempotency, and
multi-lottery isolation (BTE-14).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.app.models.bt_result import BtResult
from backend.app.models.bt_snapshot import BtSnapshot


class BtSnapshotStore:
    """bt_* read/write owner (BTE-10).

    Every write targets ``bt_*`` tables exclusively — no other tables
    are modified (BTE-02).  Lifecycle transitions are atomic within a
    single transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active(self, lottery_id: int, strategy_id: str) -> BtSnapshot | None:
        """Return the active snapshot for *(lottery_id, strategy_id)*."""
        stmt = select(BtSnapshot).where(
            BtSnapshot.lottery_id == lottery_id,
            BtSnapshot.strategy_id == strategy_id,
            BtSnapshot.status == "active",
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def find_by_fingerprint(self, fingerprint: str) -> BtSnapshot | None:
        """Return the active snapshot matching *fingerprint* (idempotency)."""
        stmt = select(BtSnapshot).where(
            BtSnapshot.fingerprint == fingerprint,
            BtSnapshot.status == "active",
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def next_version(self, lottery_id: int, strategy_id: str) -> str:
        """Return the next monotonic version string for the scope."""
        stmt = select(func.max(BtSnapshot.version)).where(
            BtSnapshot.lottery_id == lottery_id,
            BtSnapshot.strategy_id == strategy_id,
        )
        result = self._session.execute(stmt).scalar()
        if result is None:
            return "1"
        return str(int(result) + 1)

    def create_active(
        self,
        *,
        lottery_id: int,
        strategy_id: str,
        fingerprint: str,
        version: str,
        aggregate_metrics: dict[str, Any],
        window_history: list[dict[str, Any]],
        config_json: str = "{}",
    ) -> tuple[BtSnapshot, BtResult]:
        """Atomic upsert: delete old + create new active (BTE-10).

        Single transaction:
        1. Delete existing result + snapshot with same fingerprint
        2. Create new snapshot with status='active'
        3. Create result with metrics
        4. Flush

        Returns the new (snapshot, result) pair.
        """
        # 1. Delete existing rows with same fingerprint (FK requires result first)
        old_snapshot = self.find_by_fingerprint(fingerprint)
        if old_snapshot is not None:
            self._session.execute(delete(BtResult).where(BtResult.snapshot_id == old_snapshot.id))
            self._session.execute(delete(BtSnapshot).where(BtSnapshot.id == old_snapshot.id))
            self._session.flush()  # apply deletions before new inserts

        # 2. Create new snapshot
        snapshot = BtSnapshot(
            lottery_id=lottery_id,
            strategy_id=strategy_id,
            fingerprint=fingerprint,
            version=version,
            status="active",
            config_json=config_json,
        )
        self._session.add(snapshot)
        self._session.flush()  # populate snapshot.id

        # 3. Create result
        result = BtResult(
            snapshot_id=snapshot.id,
            aggregate_metrics_json=json.dumps(aggregate_metrics, default=str),
            window_history_json=json.dumps(window_history, default=str),
        )
        self._session.add(result)
        self._session.flush()

        return snapshot, result

    def mark_failed(self, fingerprint: str) -> None:
        """Mark the active snapshot as *failed* on error (BTE-10)."""
        stmt = (
            update(BtSnapshot)
            .where(
                BtSnapshot.fingerprint == fingerprint,
                BtSnapshot.status == "active",
            )
            .values(status="failed")
        )
        self._session.execute(stmt)
