"""Tests for BtSnapshotStore (BTE-10, BTE-14).

Verifies atomic writes, idempotency, lifecycle transitions, version
increment, and multi-lottery isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.backtesting.snapshot_store import BtSnapshotStore
from backend.app.models.bt_snapshot import BtSnapshot
from backend.app.repositories.base import Base


def _setup_db() -> tuple[sa.Engine, sa.MetaData]:
    """Create an in-memory SQLite DB with bt_* tables."""
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, Base.metadata


def _make_draws(n: int) -> list[dict]:
    """Create *n* draw dicts for test data."""
    base = datetime(2020, 1, 1)
    return [
        {
            "id": i,
            "draw_date": base + timedelta(weeks=i),
            "numbers": tuple(range(1, 6)),
            "super_number": 10,
        }
        for i in range(n)
    ]


class TestBtSnapshotStore:
    """Atomic writes and lifecycle (BTE-10)."""

    def test_create_active_new(self) -> None:
        engine, _ = _setup_db()
        with Session(engine) as session:
            store = BtSnapshotStore(session)
            snap, res = store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="abc123",
                version="1",
                aggregate_metrics={"hit_rate": 0.5},
                window_history=[],
            )
            session.commit()
            assert snap.status == "active"
            assert snap.fingerprint == "abc123"
            assert res.snapshot_id == snap.id

    def test_idempotent_same_fingerprint(self) -> None:
        engine, _ = _setup_db()
        with Session(engine) as session:
            store = BtSnapshotStore(session)
            s1, _ = store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="abc123",
                version="1",
                aggregate_metrics={},
                window_history=[],
            )
            s1_id = s1.id
            session.commit()

            s2, _ = store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="abc123",
                version="2",
                aggregate_metrics={},
                window_history=[],
            )
            session.commit()

            # Old snapshot deleted (upsert semantics); new snapshot active
            # SQLite may reuse the ID after delete, so verify by version
            session.expire_all()
            row = session.execute(
                select(BtSnapshot).where(BtSnapshot.id == s1_id)
            ).scalar_one_or_none()
            # Row exists but with new version (old was deleted, new inserted)
            assert row is not None
            assert row.version == "2"
            assert row.fingerprint == "abc123"
            assert s2.version == "2"

    def test_next_version_increments(self) -> None:
        engine, _ = _setup_db()
        with Session(engine) as session:
            store = BtSnapshotStore(session)
            v1 = store.next_version(1, "ml-core-5")
            assert v1 == "1"

            store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="f1",
                version="1",
                aggregate_metrics={},
                window_history=[],
            )
            session.commit()

            v2 = store.next_version(1, "ml-core-5")
            assert v2 == "2"

    def test_find_by_fingerprint(self) -> None:
        engine, _ = _setup_db()
        with Session(engine) as session:
            store = BtSnapshotStore(session)
            store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="abc123",
                version="1",
                aggregate_metrics={},
                window_history=[],
            )
            session.commit()

            found = store.find_by_fingerprint("abc123")
            assert found is not None
            assert found.fingerprint == "abc123"

            not_found = store.find_by_fingerprint("nonexistent")
            assert not_found is None

    def test_mark_failed(self) -> None:
        engine, _ = _setup_db()
        with Session(engine) as session:
            store = BtSnapshotStore(session)
            store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="abc123",
                version="1",
                aggregate_metrics={},
                window_history=[],
            )
            session.commit()

            store.mark_failed("abc123")
            session.commit()

            found = store.find_by_fingerprint("abc123")
            assert found is None  # no longer active

            # Check it's marked as failed
            stmt = select(BtSnapshot).where(BtSnapshot.fingerprint == "abc123")
            snap = session.execute(stmt).scalar_one()
            assert snap.status == "failed"

    def test_multi_lottery_isolation(self) -> None:
        """BTE-14: lottery A operations don't affect lottery B."""
        engine, _ = _setup_db()
        with Session(engine) as session:
            store = BtSnapshotStore(session)

            store.create_active(
                lottery_id=1,
                strategy_id="ml-core-5",
                fingerprint="fp_a",
                version="1",
                aggregate_metrics={},
                window_history=[],
            )
            store.create_active(
                lottery_id=2,
                strategy_id="ml-core-5",
                fingerprint="fp_b",
                version="1",
                aggregate_metrics={},
                window_history=[],
            )
            session.commit()

            # Retire lottery A's snapshot
            s1 = store.get_active(1, "ml-core-5")
            assert s1 is not None
            s1.status = "retired"
            session.commit()

            # Lottery B's snapshot should still be active
            s2 = store.get_active(2, "ml-core-5")
            assert s2 is not None
            assert s2.status == "active"
