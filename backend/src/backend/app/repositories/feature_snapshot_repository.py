"""FeatureSnapshot repository: header CRUD + active/latest resolution + versioning (PR2, FES-01).

Persistence-only primitives over the DI session; the immutable-bump and fail/retire
policy are service-owned (P2-05, mirroring statistics design §7). This repository owns
the queries the ``FeatureEngineService`` needs: resolving the current ``active`` row for a
``(lottery_id, feature_set)`` scope, the newest ``version`` for that scope, an idempotent
``active`` match by ``input_fingerprint`` (the invalidation key, design §5), and flipping
superseded snapshots to ``retired`` in the same transaction that writes a new version.

Repositories never ``commit``; the service owns the single atomic transaction (design §3).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.feature_snapshot import FeatureSnapshot
from backend.app.repositories.base_repository import BaseRepository


class FeatureSnapshotRepository(BaseRepository[FeatureSnapshot]):
    """CRUD + active/latest/idempotency/retire primitives over one DI session."""

    model = FeatureSnapshot

    def get_active(self, lottery_id: int, feature_set: str) -> FeatureSnapshot | None:
        """Return the single ``status='active'`` snapshot for a (lottery, feature_set).

        Exactly one active row per scope is enforced by the service (design §2);
        this geometric lookup reads it for the incremental/full and idempotency
        paths.
        """
        return self._session.scalar(
            select(FeatureSnapshot).where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.feature_set == feature_set,
                FeatureSnapshot.status == "active",
            )
        )

    def latest(self, lottery_id: int, feature_set: str) -> FeatureSnapshot | None:
        """Return the highest ``version`` snapshot (any status) or ``None``.

        Supplies the monotonic version source: the next version is derived from
        the newest existing row regardless of status, so a failed generation that
        bumps the counter is never reused (design §7 fail policy).
        """
        return self._session.scalar(
            select(FeatureSnapshot)
            .where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.feature_set == feature_set,
            )
            .order_by(FeatureSnapshot.version.desc())
            .limit(1)
        )

    def find_by_fingerprint(
        self,
        lottery_id: int,
        feature_set: str,
        input_fingerprint: str,
    ) -> FeatureSnapshot | None:
        """Idempotency lookup: an ``active`` snapshot already reproduces this result.

        Matches on ``input_fingerprint`` (the invalidation key, design §5) so a
        repro that would recreate an identical snapshot returns the existing row
        without writing a duplicate version (design §7 answer 2). The fingerprint
        encodes draws checksum + feature versions/params (+ optional stats).
        """
        return self._session.scalar(
            select(FeatureSnapshot).where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.feature_set == feature_set,
                FeatureSnapshot.status == "active",
                FeatureSnapshot.input_fingerprint == input_fingerprint,
            )
        )

    def next_version(self, lottery_id: int, feature_set: str) -> str:
        """Return the next monotonic ``version`` string for a scope (design §2)."""
        latest = self.latest(lottery_id, feature_set)
        if latest is None:
            return "1"
        return str(int(latest.version) + 1)

    def retire_old_active(self, lottery_id: int, feature_set: str, keep_id: int) -> int:
        """Flip every other ``active`` row to ``retired`` in the same tx (design §7).

        Exactly one ``active`` per (lottery, feature_set) is preserved: the newly
        created row (``keep_id``) stays active while prior active rows are retired.
        Called inside the creating transaction so replacement is atomic.
        """
        now = datetime.now(UTC)
        result = self._session.execute(
            update(FeatureSnapshot)
            .where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.feature_set == feature_set,
                FeatureSnapshot.status == "active",
                FeatureSnapshot.id != keep_id,
            )
            .values(status="retired", updated_at=now)
        )
        return int(result.rowcount if result.rowcount is not None else 0)

    def create_snapshot(
        self,
        *,
        lottery_id: int,
        feature_set: str,
        version: str,
        feature_engine_version: str,
        checksum: str,
        input_fingerprint: str,
        status: str,
        is_locked: bool,
        draw_count: int,
        draws_from: int,
        draws_to: int,
    ) -> FeatureSnapshot:
        """Insert one snapshot header via the generic ``create`` (flush surfaces UNIQUE)."""
        return self.create(
            {
                "lottery_id": lottery_id,
                "feature_set": feature_set,
                "version": version,
                "feature_engine_version": feature_engine_version,
                "checksum": checksum,
                "input_fingerprint": input_fingerprint,
                "status": status,
                "is_locked": is_locked,
                "draw_count": draw_count,
                "draws_from": draws_from,
                "draws_to": draws_to,
            }
        )

    @staticmethod
    def session_for(db_session: Session) -> FeatureSnapshotRepository:
        """Return a repository bound to ``db_session`` (DI convenience)."""
        return FeatureSnapshotRepository(db_session)
