"""Tests for generator snapshot store — lifecycle, idempotency, atomic writes (GEN-007, GEN-008).

Spec refs: GEN-007 (lifecycle), GEN-008 (fingerprint idempotency).
Design refs: GenSnapshotStore, Migration 0015.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.generators.snapshot_store import GenSnapshotStore
from backend.app.models.gen_snapshot import GenSnapshot

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


@pytest.fixture
def gen_session(tmp_path: Path) -> sessionmaker[Session]:
    """Migrated SQLite DB with gen_* tables for snapshot store tests."""
    db = tmp_path / "gen_test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def session(gen_session: sessionmaker[Session]) -> Session:
    """Single session from the migrated test DB."""
    s = gen_session()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def store(session: Session) -> GenSnapshotStore:
    """GenSnapshotStore bound to the test session."""
    return GenSnapshotStore(session)


@pytest.fixture
def seeded(session: Session) -> None:
    """Seed the default lottery and selection rows for FK constraints."""
    _seed_lottery(session)
    _seed_selection(session)


def _seed_lottery(session: Session, lottery_id: int = 1) -> None:
    """Insert a minimal lottery row for FK constraints."""
    session.execute(
        text(
            "INSERT INTO lottery "
            "(id, code, name, country, min_number, max_number, numbers_to_select, "
            "super_number_min, super_number_max, created_at) "
            "VALUES (:id, :code, :name, :country, :min_n, :max_n, :num_sel, "
            ":sn_min, :sn_max, :created_at)"
        ),
        {
            "id": lottery_id,
            "code": f"LOT{lottery_id}",
            "name": f"Lottery {lottery_id}",
            "country": "AR",
            "min_n": 1,
            "max_n": 49,
            "num_sel": 6,
            "sn_min": 1,
            "sn_max": 9,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    session.flush()


def _seed_selection(session: Session, lottery_id: int = 1, selection_id: int = 1) -> None:
    """Insert a minimal meta_selections row for FK constraints."""
    session.execute(
        text(
            "INSERT INTO meta_selections "
            "(id, lottery_id, context_hash, version, status, fingerprint, created_at) "
            "VALUES (:id, :lottery_id, :ctx, :ver, :status, :fp, :created_at)"
        ),
        {
            "id": selection_id,
            "lottery_id": lottery_id,
            "ctx": "test_hash",
            "ver": "1",
            "status": "active",
            "fp": "test_fp",
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    session.flush()


def _create_snapshot(
    store: GenSnapshotStore,
    *,
    lottery_id: int = 1,
    selection_id: int = 1,
    version: str = "1",
    fingerprint: str,
    config_json: dict | None = None,
    combinations: list[dict] | None = None,
) -> int:
    """Create an active snapshot with minimal per-scope defaults."""
    return store.create_active_snapshot(
        lottery_id=lottery_id,
        selection_id=selection_id,
        version=version,
        fingerprint=fingerprint,
        config_json=config_json,
        combinations=combinations or [],
    )


class TestNextVersion:
    """next_version() — monotonic versioning per (lottery_id, selection_id)."""

    def test_first_version_is_one(self, store: GenSnapshotStore, seeded: None) -> None:
        """No existing versions → '1'."""
        assert store.next_version(1, 1) == "1"

    def test_monotonic_increment(
        self, store: GenSnapshotStore, session: Session, seeded: None
    ) -> None:
        """After creating v1, next is v2."""
        _create_snapshot(store, fingerprint="fp1")
        session.commit()
        assert store.next_version(1, 1) == "2"

    def test_lottery_isolation(self, store: GenSnapshotStore, session: Session) -> None:
        """Version is per (lottery_id, selection_id), not global."""
        _seed_lottery(session, 1)
        _seed_lottery(session, 2)
        _seed_selection(session, 1, 1)
        _seed_selection(session, 2, 2)
        _create_snapshot(store, fingerprint="fp1")
        session.commit()
        # lottery 2 has no versions yet
        assert store.next_version(2, 2) == "1"


class TestFingerprintIdempotency:
    """find_by_fingerprint() — GEN-008 idempotency."""

    def test_existing_fingerprint_returns_snapshot(
        self, store: GenSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Same fingerprint → return existing active snapshot, no new rows."""
        _create_snapshot(store, fingerprint="abc123")
        session.commit()
        found = store.find_by_fingerprint("abc123")
        assert found is not None
        assert found.fingerprint == "abc123"

    def test_unknown_fingerprint_returns_none(self, store: GenSnapshotStore, seeded: None) -> None:
        """Unknown fingerprint → None."""
        assert store.find_by_fingerprint("unknown") is None


class TestLifecycle:
    """Lifecycle transitions: active → retired (GEN-007)."""

    def test_retire_active(self, store: GenSnapshotStore, session: Session, seeded: None) -> None:
        """retire_active changes status to 'retired'."""
        snap_id = _create_snapshot(store, fingerprint="fp1")
        session.commit()
        store.retire_active(1, 1)
        session.commit()
        snap = session.get(GenSnapshot, snap_id)
        assert snap is not None
        assert snap.status == "retired"

    def test_active_to_retired_atomic(
        self, store: GenSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Create new active retires old active atomically."""
        old_id = _create_snapshot(store, version="1", fingerprint="fp_old")
        session.commit()
        new_id = _create_snapshot(store, version="2", fingerprint="fp_new")
        session.commit()
        old = session.get(GenSnapshot, old_id)
        new = session.get(GenSnapshot, new_id)
        assert old is not None
        assert new is not None
        assert old.status == "retired"
        assert new.status == "active"


class TestAtomicWrite:
    """Atomic writes — rollback leaves DB clean."""

    def test_rollback_leaves_db_clean(self, gen_session: sessionmaker[Session]) -> None:
        """Failed transaction doesn't leave partial rows."""
        s = gen_session()
        _seed_lottery(s)
        _seed_selection(s)
        s.commit()
        try:
            store = GenSnapshotStore(s)
            _create_snapshot(store, fingerprint="fp_rollback")
            # Force a rollback
            s.rollback()
        except Exception:
            s.rollback()

        # Verify no snapshot was persisted
        s2 = gen_session()
        try:
            count = s2.query(GenSnapshot).filter(GenSnapshot.fingerprint == "fp_rollback").count()
            assert count == 0
        finally:
            s2.close()

    def test_combinations_persisted_with_snapshot(
        self, store: GenSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Snapshot + combinations created atomically."""
        combos = [
            {"position": 0, "numbers": "[1,2,3,4,5,6]", "super_number": 7, "score": None},
            {"position": 1, "numbers": "[7,8,9,10,11,12]", "super_number": None, "score": 0.85},
        ]
        snap_id = _create_snapshot(
            store,
            fingerprint="fp_atomic",
            config_json={"key": "value"},
            combinations=combos,
        )
        session.commit()
        snap = session.get(GenSnapshot, snap_id)
        assert snap is not None
        assert snap.config_json == json.dumps({"key": "value"})
        stored_combos = store.get_combinations(snap_id)
        assert len(stored_combos) == 2


class TestGetSnapshots:
    """get_snapshots() — list all snapshots for a lottery."""

    def test_returns_snapshots_ordered_by_version(
        self, store: GenSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Snapshots ordered by version DESC."""
        _create_snapshot(store, version="1", fingerprint="fp1")
        _create_snapshot(store, version="2", fingerprint="fp2")
        session.commit()
        snapshots = store.get_snapshots(1)
        assert len(snapshots) == 2
        assert snapshots[0].version == "2"
        assert snapshots[1].version == "1"

    def test_lottery_isolation(self, store: GenSnapshotStore, session: Session) -> None:
        """Only returns snapshots for the requested lottery."""
        _seed_lottery(session, 1)
        _seed_lottery(session, 2)
        _seed_selection(session, 1, 1)
        _seed_selection(session, 2, 2)
        _create_snapshot(store, fingerprint="fp1")
        _create_snapshot(store, lottery_id=2, selection_id=2, fingerprint="fp2")
        session.commit()
        assert len(store.get_snapshots(1)) == 1
        assert len(store.get_snapshots(2)) == 1
