"""Snapshot store for Generator module — gen_* I/O owner (GEN-007, GEN-008).

Manages lifecycle of gen_snapshots and gen_combinations:
atomic writes, lifecycle transitions (active|retired|failed),
monotonic versioning per (lottery_id, selection_id), and
fingerprint idempotency (same fingerprint → return existing).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.gen_combination import GenCombination
from backend.app.models.gen_snapshot import GenSnapshot


class GenSnapshotStore:
    """I/O owner for gen_* tables (GEN-007, GEN-008, GEN-012).

    Handles version computation, fingerprint idempotency checks,
    lifecycle transitions, and atomic writes.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def next_version(self, lottery_id: int, selection_id: int) -> str:
        """Compute next monotonic version for (lottery_id, selection_id) (GEN-007).

        Returns "1" if no existing versions, else max(version) + 1 as string.
        """
        stmt = (
            select(GenSnapshot.version)
            .where(
                GenSnapshot.lottery_id == lottery_id,
                GenSnapshot.selection_id == selection_id,
            )
            .order_by(GenSnapshot.version.desc())
            .limit(1)
        )
        last = self._session.execute(stmt).scalar_one_or_none()
        if last is None:
            return "1"
        return str(int(last) + 1)

    # ------------------------------------------------------------------
    # Fingerprint lookup
    # ------------------------------------------------------------------

    def find_by_fingerprint(self, fingerprint: str) -> GenSnapshot | None:
        """Find an active snapshot by fingerprint (GEN-008).

        Returns the existing active record if found, None otherwise.
        """
        stmt = (
            select(GenSnapshot)
            .where(
                GenSnapshot.fingerprint == fingerprint,
                GenSnapshot.status == "active",
            )
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def retire_active(self, lottery_id: int, selection_id: int) -> None:
        """Retire the currently active snapshot for (lottery_id, selection_id) (GEN-007)."""
        stmt = (
            update(GenSnapshot)
            .where(
                GenSnapshot.lottery_id == lottery_id,
                GenSnapshot.selection_id == selection_id,
                GenSnapshot.status == "active",
            )
            .values(status="retired")
        )
        self._session.execute(stmt)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def create_active_snapshot(
        self,
        *,
        lottery_id: int,
        selection_id: int,
        version: str,
        fingerprint: str,
        config_json: dict[str, Any] | None,
        combinations: list[dict[str, Any]],
    ) -> int:
        """Create an active snapshot with combinations atomically (GEN-007, GEN-008).

        Retires any existing active snapshot for (lottery_id, selection_id).
        Returns the new snapshot ID.
        """
        # Retire existing active
        self.retire_active(lottery_id, selection_id)

        # Create snapshot
        snapshot = GenSnapshot(
            lottery_id=lottery_id,
            selection_id=selection_id,
            version=version,
            status="active",
            fingerprint=fingerprint,
            config_json=json.dumps(config_json) if config_json else None,
        )
        self._session.add(snapshot)
        self._session.flush()

        # Create combinations
        for combo in combinations:
            row = GenCombination(
                snapshot_id=snapshot.id,
                position=combo["position"],
                numbers=combo["numbers"],
                super_number=combo.get("super_number"),
                score=combo.get("score"),
            )
            self._session.add(row)

        self._session.flush()
        return snapshot.id

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_snapshots(self, lottery_id: int) -> list[GenSnapshot]:
        """Get all snapshots for a lottery, ordered by version DESC (GEN-007)."""
        stmt = (
            select(GenSnapshot)
            .where(GenSnapshot.lottery_id == lottery_id)
            .order_by(GenSnapshot.version.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_combinations(self, snapshot_id: int) -> list[GenCombination]:
        """Get all combinations for a snapshot, ordered by position."""
        stmt = (
            select(GenCombination)
            .where(GenCombination.snapshot_id == snapshot_id)
            .order_by(GenCombination.position)
        )
        return list(self._session.execute(stmt).scalars().all())
