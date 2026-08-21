"""Tests for ProbabilityService and SnapshotStore (PR2b, T-11/T-12).

Fixture-driven: uses in-memory SQLite with real ORM models.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.prob_snapshot import ProbSnapshot
from backend.app.models.prob_value import ProbValue
from backend.app.probability.snapshot_store import SnapshotStore
from backend.app.repositories.base import Base


@pytest.fixture()
def engine():
    """Create an in-memory SQLite engine with all models."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    """Create a session for testing."""
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.close()


@pytest.fixture()
def store(session):
    """Create a SnapshotStore for testing."""
    return SnapshotStore(session)


# --- SnapshotStore tests (T-11) ---


class TestSnapshotStoreLifecycle:
    """Lifecycle: active→retired, failed header never active."""

    def test_create_and_get_active(self, store, session):
        snap = store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="abc", input_fingerprint="def",
            status="active", is_locked=True, draw_count=10, draws_from=1, draws_to=10,
        )
        session.flush()
        result = store.get_active(1, "core")
        assert result is not None
        assert result.id == snap.id
        assert result.status == "active"

    def test_retire_old_active(self, store, session):
        old = store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="old", input_fingerprint="old",
            status="active", is_locked=True, draw_count=10, draws_from=1, draws_to=10,
        )
        session.flush()
        new = store.create_snapshot(
            lottery_id=1, model_set="core", version="2",
            prob_generator_version="1.0.0", checksum="new", input_fingerprint="new",
            status="active", is_locked=True, draw_count=10, draws_from=1, draws_to=10,
        )
        session.flush()
        store.retire_old_active(1, "core", keep_id=new.id)
        session.flush()
        assert store.get_active(1, "core").id == new.id
        old_refreshed = session.get(ProbSnapshot, old.id)
        assert old_refreshed.status == "retired"

    def test_mark_failed(self, store, session):
        snap = store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="", input_fingerprint="",
            status="active", is_locked=True, draw_count=0, draws_from=0, draws_to=0,
        )
        session.flush()
        store.mark_failed(snap.id)
        session.flush()
        refreshed = session.get(ProbSnapshot, snap.id)
        assert refreshed.status == "failed"
        assert refreshed.is_locked is False

    def test_next_version_increments(self, store, session):
        store.create_snapshot(
            lottery_id=1, model_set="core", version="3",
            prob_generator_version="1.0.0", checksum="", input_fingerprint="",
            status="active", is_locked=True, draw_count=0, draws_from=0, draws_to=0,
        )
        session.flush()
        assert store.next_version(1, "core") == "4"

    def test_next_version_starts_at_one(self, store):
        assert store.next_version(99, "core") == "1"

    def test_find_by_fingerprint_match(self, store, session):
        store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="c", input_fingerprint="fp123",
            status="active", is_locked=True, draw_count=0, draws_from=0, draws_to=0,
        )
        session.flush()
        result = store.find_by_fingerprint(1, "core", "fp123")
        assert result is not None

    def test_find_by_fingerprint_no_match(self, store, session):
        store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="c", input_fingerprint="fp123",
            status="active", is_locked=True, draw_count=0, draws_from=0, draws_to=0,
        )
        session.flush()
        assert store.find_by_fingerprint(1, "core", "nope") is None

    def test_bulk_insert_and_read(self, store, session):
        snap = store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="c", input_fingerprint="f",
            status="active", is_locked=True, draw_count=2, draws_from=1, draws_to=2,
        )
        session.flush()
        rows = [
            ProbValue(model_id="m1", model_version="1.0.0", subject="s1",
                      draw_number=None, value=__import__("decimal").Decimal("0.5"),
                      params_json="{}"),
            ProbValue(model_id="m1", model_version="1.0.0", subject="s2",
                      draw_number=None, value=__import__("decimal").Decimal("0.3"),
                      params_json="{}"),
        ]
        store.bulk_insert_values(snap.id, rows)
        session.flush()
        result = store.values_for_snapshot(snap.id)
        assert len(result) == 2
        assert result[0].subject == "s1"

    def test_values_ordered(self, store, session):
        snap = store.create_snapshot(
            lottery_id=1, model_set="core", version="1",
            prob_generator_version="1.0.0", checksum="c", input_fingerprint="f",
            status="active", is_locked=True, draw_count=0, draws_from=0, draws_to=0,
        )
        session.flush()
        from decimal import Decimal
        rows = [
            ProbValue(model_id="m2", model_version="1.0.0", subject="b",
                      draw_number=None, value=Decimal("1"), params_json="{}"),
            ProbValue(model_id="m1", model_version="1.0.0", subject="a",
                      draw_number=None, value=Decimal("2"), params_json="{}"),
        ]
        store.bulk_insert_values(snap.id, rows)
        session.flush()
        result = store.values_for_snapshot(snap.id)
        assert result[0].model_id == "m1"
        assert result[1].model_id == "m2"

    def test_empty_get_active_returns_none(self, store):
        assert store.get_active(999, "core") is None
