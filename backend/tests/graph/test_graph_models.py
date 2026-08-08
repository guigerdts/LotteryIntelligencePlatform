"""Graph ORM model tests (REQ-07, GES-06) — MINIMAL SET for PR1b.

Tests for GraphSnapshot and GraphValue entities following the
prob_snapshot/prob_value pattern (F5 precedent). Covers:
- Basic creation
- Decimal round-trip (Numeric(20,8))
- Unique constraint enforcement
- Nullable draw_number for grid rows

EXHAUSTIVE tests (CHECK constraints, FK RESTRICT, cross-snapshot) are
in PR4 (Task 9/10) under tests/graph/test_graph_persistence.py.
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


class TestGraphSnapshot:
    """Minimal tests for GraphSnapshot ORM model (PR1b)."""

    def test_create_snapshot(self, db_session: Session, lottery: Lottery) -> None:
        """Basic snapshot creation succeeds."""
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
        assert snap.id is not None
        assert snap.graph_type == "cooccurrence"

    def test_unique_constraint_scope_version(self, db_session: Session, lottery: Lottery) -> None:
        """Duplicate (lottery_id, graph_type, version) raises IntegrityError."""
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
        db_session.add(snap1)
        db_session.commit()

        snap2 = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="cooccurrence",
            version="1",
            graph_generator_version="1.0.0",
            checksum="c" * 64,
            input_fingerprint="d" * 64,
            params_json="{}",
            status="retired",
            is_locked=False,
            draw_count=50,
            draws_from=1,
            draws_to=50,
        )
        db_session.add(snap2)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()


class TestGraphValue:
    """Minimal tests for GraphValue ORM model (PR1b)."""

    def test_decimal_round_trip(self, db_session: Session, lottery: Lottery) -> None:
        """Decimal(20,8) persists and round-trips exactly."""
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

        original_value = Decimal("0.12345678")
        val = GraphValue(
            snapshot_id=snap.id,
            metric_type="cooccurrence",
            subject="1-2",
            draw_number=1,
            value=original_value,
            params_json="{}",
        )
        db_session.add(val)
        db_session.commit()

        loaded = db_session.get(GraphValue, val.id)
        assert loaded is not None
        assert loaded.value == original_value
        assert loaded.value == Decimal("0.12345678")

    def test_nullable_draw_number(self, db_session: Session, lottery: Lottery) -> None:
        """draw_number is NULLable for grid rows (D-A4)."""
        snap = GraphSnapshot(
            lottery_id=lottery.id,
            graph_type="centrality",
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
            metric_type="centrality_degree",
            subject="node_5",
            draw_number=None,
            value=Decimal("0.25000000"),
            params_json="{}",
        )
        db_session.add(val)
        db_session.commit()

        loaded = db_session.get(GraphValue, val.id)
        assert loaded is not None
        assert loaded.draw_number is None

    def test_unique_constraint_cell(self, db_session: Session, lottery: Lottery) -> None:
        """Duplicate (snapshot_id, metric_type, subject, draw_number) raises IntegrityError."""
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

        val1 = GraphValue(
            snapshot_id=snap.id,
            metric_type="cooccurrence",
            subject="1-2",
            draw_number=1,
            value=Decimal("5.00000000"),
            params_json="{}",
        )
        db_session.add(val1)
        db_session.commit()

        val2 = GraphValue(
            snapshot_id=snap.id,
            metric_type="cooccurrence",
            subject="1-2",
            draw_number=1,
            value=Decimal("10.00000000"),
            params_json="{}",
        )
        db_session.add(val2)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()
