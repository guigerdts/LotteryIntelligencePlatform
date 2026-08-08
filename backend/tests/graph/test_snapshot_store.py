"""Tests for graph snapshot store (REQ-07, Task 9).

Tests cover:
- Save/load snapshot
- Fingerprint-based lookup
- Upsert lifecycle
- Empty snapshot handling
- Values persistence
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.graph.snapshot_store import (
    load_snapshot_by_fingerprint,
    load_snapshot_values,
    retire_snapshot,
    save_snapshot,
    upsert_snapshot,
)
from backend.app.models import Base
from backend.app.models.lottery import Lottery


@pytest.fixture()
def db_session() -> Session:
    """Create an in-memory SQLite session with the schema and FK enforcement."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def lottery(db_session: Session) -> Lottery:
    """Create a lottery for FK references."""
    lot = Lottery(
        id=1,
        code="BAL",
        name="Baloto",
        country="CO",
        min_number=1,
        max_number=45,
        numbers_to_select=5,
        super_number_min=1,
        super_number_max=16,
    )
    db_session.add(lot)
    db_session.commit()
    return lot


class TestSaveSnapshot:
    """Tests for save_snapshot."""

    def test_basic_save(self, db_session: Session, lottery: Lottery) -> None:
        """Basic snapshot save works."""
        values = [
            ("cooccurrence", "1-2", 1, Decimal("5.00000000"), "{}"),
            ("cooccurrence", "1-3", 2, Decimal("3.00000000"), "{}"),
        ]
        snap = save_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 100, 1, 100, values,
        )

        assert snap.id is not None
        assert snap.graph_type == "cooccurrence"
        assert snap.status == "active"

    def test_values_persisted(self, db_session: Session, lottery: Lottery) -> None:
        """Values are persisted with snapshot."""
        values = [
            ("cooccurrence", "1-2", 1, Decimal("5.00000000"), "{}"),
        ]
        snap = save_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 100, 1, 100, values,
        )

        loaded_values = load_snapshot_values(db_session, snap.id)
        assert len(loaded_values) == 1
        assert loaded_values[0].metric_type == "cooccurrence"
        assert loaded_values[0].value == Decimal("5.00000000")


class TestLoadSnapshot:
    """Tests for load_snapshot_by_fingerprint."""

    def test_load_by_fingerprint(self, db_session: Session, lottery: Lottery) -> None:
        """Load snapshot by fingerprint."""
        save_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 100, 1, 100, [],
        )

        loaded = load_snapshot_by_fingerprint(db_session, lottery.id, "cooccurrence", "b" * 64)
        assert loaded is not None
        assert loaded.id is not None

    def test_load_nonexistent(self, db_session: Session, lottery: Lottery) -> None:
        """Load nonexistent fingerprint returns None."""
        loaded = load_snapshot_by_fingerprint(db_session, lottery.id, "cooccurrence", "x" * 64)
        assert loaded is None


class TestUpsertSnapshot:
    """Tests for upsert_snapshot."""

    def test_upsert_creates_new(self, db_session: Session, lottery: Lottery) -> None:
        """Upsert creates new snapshot."""
        snap = upsert_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 100, 1, 100, [],
        )
        assert snap.id is not None
        assert snap.status == "active"

    def test_upsert_retires_old(self, db_session: Session, lottery: Lottery) -> None:
        """Upsert retires old active snapshot."""
        snap1 = upsert_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 100, 1, 100, [],
        )
        snap2 = upsert_snapshot(
            db_session, lottery.id, "cooccurrence", "2", "1.0.0",
            "c" * 64, "d" * 64, "{}", 100, 1, 100, [],
        )

        # snap1 should be retired
        db_session.refresh(snap1)
        assert snap1.status == "retired"
        # snap2 should be active
        assert snap2.status == "active"
        assert snap2.id != snap1.id


class TestRetireSnapshot:
    """Tests for retire_snapshot."""

    def test_retire(self, db_session: Session, lottery: Lottery) -> None:
        """Retire snapshot sets status to 'retired'."""
        snap = save_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 100, 1, 100, [],
        )

        retire_snapshot(db_session, snap.id)
        db_session.refresh(snap)
        assert snap.status == "retired"


class TestEmptySnapshot:
    """Tests for empty snapshot handling."""

    def test_empty_values(self, db_session: Session, lottery: Lottery) -> None:
        """Empty values list is valid."""
        snap = save_snapshot(
            db_session, lottery.id, "cooccurrence", "1", "1.0.0",
            "a" * 64, "b" * 64, "{}", 0, 0, 0, [],
        )
        assert snap.id is not None
        values = load_snapshot_values(db_session, snap.id)
        assert values == []
