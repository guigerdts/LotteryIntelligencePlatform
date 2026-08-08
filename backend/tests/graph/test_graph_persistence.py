"""Graph ORM persistence tests (REQ-07, GES-06) — EXHAUSTIVE SET for PR4.

Moved from test_graph_models.py (PR1b) to PR4 (Task 9/10) to maintain <=400 LOC
per PR. These tests cover:
- CHECK constraints (range, status)
- FK RESTRICT enforcement
- Cross-snapshot validation

MINIMAL tests (basic creation, UNQ, Decimal, nullable) are in PR1b
under tests/graph/test_graph_models.py.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session

from backend.app.models import Base
from backend.app.models.graph_snapshot import GraphSnapshot
from backend.app.models.graph_value import GraphValue
from backend.app.models.lottery import Lottery


@pytest.fixture()
def db_session() -> Session:
    """Create an in-memory SQLite session with the schema and FK enforcement."""
    engine = create_engine("sqlite:///:memory:")
    # Enable FK enforcement (SQLite disables it by default).
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


class TestGraphSnapshotPersistence:
    """Exhaustive tests for GraphSnapshot ORM constraints (PR4, Task 9)."""

    def test_check_constraint_range(self, db_session: Session, lottery: Lottery) -> None:
        """draws_from > draws_to violates CHECK constraint."""
        snap = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="1",
            graph_generator_version="1.0.0",
            checksum="a" * 64,
            input_fingerprint="b" * 64,
            params_json="{}",
            status="active",
            is_locked=False,
            draw_count=0,
            draws_from=100,
            draws_to=1,
        )
        db_session.add(snap)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()

    def test_check_constraint_status(self, db_session: Session, lottery: Lottery) -> None:
        """Invalid status violates CHECK constraint."""
        snap = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="1",
            graph_generator_version="1.0.0",
            checksum="a" * 64,
            input_fingerprint="b" * 64,
            params_json="{}",
            status="invalid_status",
            is_locked=False,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db_session.add(snap)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()

    def test_fk_restrict_lottery(self, db_session: Session, lottery: Lottery) -> None:
        """Deleting lottery with snapshots raises IntegrityError (FK RESTRICT)."""
        snap = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="1",
            graph_generator_version="1.0.0",
            checksum="a" * 64,
            input_fingerprint="b" * 64,
            params_json="{}",
            status="active",
            is_locked=False,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db_session.add(snap)
        db_session.commit()

        db_session.delete(lottery)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()


class TestGraphValuePersistence:
    """Exhaustive tests for GraphValue ORM constraints (PR4, Task 10)."""

    def test_fk_restrict_snapshot(self, db_session: Session, lottery: Lottery) -> None:
        """Deleting snapshot with values raises IntegrityError (FK RESTRICT)."""
        snap = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="1",
            graph_generator_version="1.0.0",
            checksum="a" * 64,
            input_fingerprint="b" * 64,
            params_json="{}",
            status="active",
            is_locked=False,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db_session.add(snap)
        db_session.commit()

        val = GraphValue(
            snapshot_id=snap.id,
            metric_type="cooccurrence",
            subject="1-2",
            draw_number=1,
            value=Decimal("5.00000000"),
            params_json="{}",
        )
        db_session.add(val)
        db_session.commit()

        db_session.delete(snap)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()

    def test_different_snapshots_same_cell_allowed(
        self, db_session: Session, lottery: Lottery
    ) -> None:
        """Same (metric_type, subject, draw_number) allowed across different snapshots."""
        snap1 = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="1",
            graph_generator_version="1.0.0",
            checksum="a" * 64,
            input_fingerprint="b" * 64,
            params_json="{}",
            status="active",
            is_locked=False,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        snap2 = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="2",
            graph_generator_version="1.0.0",
            checksum="c" * 64,
            input_fingerprint="d" * 64,
            params_json="{}",
            status="retired",
            is_locked=False,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db_session.add_all([snap1, snap2])
        db_session.commit()

        val1 = GraphValue(
            snapshot_id=snap1.id,
            metric_type="cooccurrence",
            subject="1-2",
            draw_number=1,
            value=Decimal("5.00000000"),
            params_json="{}",
        )
        val2 = GraphValue(
            snapshot_id=snap2.id,
            metric_type="cooccurrence",
            subject="1-2",
            draw_number=1,
            value=Decimal("10.00000000"),
            params_json="{}",
        )
        db_session.add_all([val1, val2])
        db_session.commit()

        assert val1.id != val2.id
        assert val1.snapshot_id != val2.snapshot_id
