"""Tests for DlSnapshotStore — flush-only dl_* I/O owner lifecycle and gotchas.

Spec refs: REQ-09 (portable), DLE-01/09/12. Design refs: DlSnapshotStore contract
(ADR-1 flush-only, ADR-2 delete-not-mark retirement, post-rollback mark_failed
recreate-pattern gotcha).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.dl.snapshot_store import DlSnapshotStore
from backend.app.models.dl_metric import DlMetric
from backend.app.models.dl_snapshot import DlSnapshot
from backend.app.models.dl_weight import DlWeight

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


@pytest.fixture
def db_factory(tmp_path: Path) -> sessionmaker[Session]:
    """Migrated SQLite DB with the full head schema (incl. dl_* tables)."""
    db = tmp_path / "dl_store_test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def session(db_factory: sessionmaker[Session]) -> Session:
    """Single session from the migrated test DB."""
    s = db_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def store(session: Session) -> DlSnapshotStore:
    """DlSnapshotStore bound to the test session."""
    return DlSnapshotStore(session)


@pytest.fixture
def seeded(session: Session) -> None:
    """Seed and COMMIT the lottery row so rollbacks keep the FK target alive."""
    _seed_lottery(session)
    session.commit()


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
            "max_n": 45,
            "num_sel": 4,
            "sn_min": 1,
            "sn_max": 3,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    session.flush()


def _make_snapshot(store: DlSnapshotStore, **overrides: object) -> DlSnapshot:
    """Create an active snapshot header with per-scope test defaults."""
    kwargs: dict[str, object] = {
        "lottery_id": 1,
        "model_set": "core-3",
        "version": "1",
        "dl_generator_version": "dl-test-1",
        "draw_count": 100,
        "draws_from": 1,
        "draws_to": 100,
    }
    kwargs.update(overrides)
    return store.create_snapshot(**kwargs)  # type: ignore[arg-type]


def _make_metric(model_id: str, metric_name: str, value: Decimal) -> DlMetric:
    """Build a detached DlMetric row (store stamps snapshot_id)."""
    return DlMetric(
        model_id=model_id,
        model_version="1.0.0",
        number=0,
        metric_name=metric_name,
        value=value,
        params_json='{"epochs": 3}',
    )


def _make_weight(snapshot_id: int, model_id: str = "mlp") -> DlWeight:
    """Build a small in-format DlWeight row."""
    blob = b"\x89DLW-fake-tensor-data"
    return DlWeight(
        snapshot_id=snapshot_id,
        model_id=model_id,
        weights_blob=blob,
        weights_size_bytes=len(blob),
        weights_fingerprint="runfp123",
        format_version=1,
    )


def _snapshot_count(factory: sessionmaker[Session]) -> int:
    """Committed dl_snapshots row count seen through a FRESH connection."""
    observer = factory()
    try:
        return int(observer.execute(select(func.count()).select_from(DlSnapshot)).scalar_one())
    finally:
        observer.close()


class TestGetActive:
    """get_active — newest ACTIVE snapshot per (lottery_id, model_set)."""

    def test_no_active_returns_none(self, store: DlSnapshotStore, seeded: None) -> None:
        """Empty scope → None (no crash on missing rows)."""
        assert store.get_active(1, "core-3") is None

    def test_returns_newest_active_by_version_desc(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Two active versions → highest version wins."""
        _make_snapshot(store, version="1")
        newest = _make_snapshot(store, version="2")
        session.commit()
        found = store.get_active(1, "core-3")
        assert found is not None
        assert found.id == newest.id
        assert found.version == "2"

    def test_scope_isolated_per_lottery_and_model_set(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Each (lottery_id, model_set) scope resolves independently."""
        _seed_lottery(session, 2)
        _make_snapshot(store, lottery_id=1, version="1")
        _make_snapshot(store, lottery_id=2, model_set="core-5", version="7")
        session.commit()
        assert store.get_active(1, "core-3").version == "1"  # type: ignore[union-attr]
        assert store.get_active(2, "core-5").version == "7"  # type: ignore[union-attr]
        assert store.get_active(2, "core-3") is None


class TestFindByFingerprint:
    """find_by_fingerprint — active-only idempotency lookup (DLE-12 rerun)."""

    def test_active_match_returns_snapshot(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Matching active fingerprint → that snapshot."""
        snap = _make_snapshot(store, input_fingerprint="abc123")
        session.commit()
        found = store.find_by_fingerprint(1, "core-3", "abc123")
        assert found is not None
        assert found.id == snap.id

    def test_retired_fingerprint_does_not_match(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """A retired row carrying the fingerprint is invisible (active-only)."""
        old = _make_snapshot(store, version="1", input_fingerprint="dup")
        new = _make_snapshot(store, version="2", input_fingerprint="fresh")
        session.commit()
        store.retire_old_active(1, "core-3", keep_id=new.id)
        session.commit()
        assert old.status == "retired"
        assert store.find_by_fingerprint(1, "core-3", "dup") is None
        assert store.find_by_fingerprint(1, "core-3", "fresh") is not None

    def test_unknown_fingerprint_returns_none(self, store: DlSnapshotStore, seeded: None) -> None:
        """No row carries the fingerprint → None."""
        assert store.find_by_fingerprint(1, "core-3", "missing") is None


class TestNextVersion:
    """next_version — monotonic per-scope versioning."""

    def test_first_version_is_one(self, store: DlSnapshotStore, seeded: None) -> None:
        """No existing versions → '1'."""
        assert store.next_version(1, "core-3") == "1"

    def test_increment_after_existing(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Existing max version → max + 1."""
        _make_snapshot(store, version="1")
        session.commit()
        assert store.next_version(1, "core-3") == "2"

    def test_scopes_do_not_share_counter(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """A version consumed in one scope leaves the other at '1'."""
        _make_snapshot(store, model_set="core-3", version="1")
        session.commit()
        assert store.next_version(1, "core-5") == "1"


class TestCreateSnapshotFlushOnly:
    """create_snapshot — flush-only discipline (ADR-1: caller owns commit)."""

    def test_flush_assigns_identity_and_session_visibility(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Returned header carries a DB-assigned id before any commit."""
        snap = _make_snapshot(store)
        assert snap.id is not None
        assert session.get(DlSnapshot, snap.id) is not None

    def test_placeholder_defaults_are_empty_and_locked(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Placeholders: empty checksum/fp, cut/window 0, active + locked."""
        snap = _make_snapshot(store)
        session.expire(snap)
        refreshed = session.get(DlSnapshot, snap.id)
        assert refreshed is not None
        assert refreshed.checksum == ""
        assert refreshed.input_fingerprint == ""
        assert refreshed.cut == 0
        assert refreshed.window == 0
        assert refreshed.status == "active"
        assert refreshed.is_locked is True

    def test_nothing_persists_until_caller_commits(
        self,
        store: DlSnapshotStore,
        session: Session,
        db_factory: sessionmaker[Session],
        seeded: None,
    ) -> None:
        """Uncommitted store writes are invisible outside the session (no inner commit)."""
        _make_snapshot(store, version="1")
        assert _snapshot_count(db_factory) == 0
        session.commit()
        assert _snapshot_count(db_factory) == 1


class TestBulkInsertMetrics:
    """bulk_insert_metrics + metrics_for_snapshot — exact Decimal payload rows."""

    def test_decimal_rows_roundtrip_exact(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Decimal values persist and read back as Decimal, ordered per contract."""
        snap = _make_snapshot(store)
        store.bulk_insert_metrics(
            snap.id,
            [
                _make_metric("lstm", "f1", Decimal("0.66666667")),
                _make_metric("mlp", "accuracy", Decimal("0.81250000")),
            ],
        )
        session.commit()
        rows = store.metrics_for_snapshot(snap.id)
        # Contract order: (model_id, metric_name) ascending.
        assert [(r.model_id, r.metric_name) for r in rows] == [("lstm", "f1"), ("mlp", "accuracy")]
        assert isinstance(rows[0].value, Decimal)
        assert rows[1].value == Decimal("0.81250000")
        assert rows[0].value == Decimal("0.66666667")

    def test_metrics_filter_by_model_id(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """model_id filter narrows to one family without touching others."""
        snap = _make_snapshot(store)
        store.bulk_insert_metrics(
            snap.id,
            [
                _make_metric("mlp", "accuracy", Decimal("0.80000000")),
                _make_metric("lstm", "accuracy", Decimal("0.70000000")),
            ],
        )
        session.commit()
        mlp_rows = store.metrics_for_snapshot(snap.id, model_id="mlp")
        assert len(mlp_rows) == 1
        assert mlp_rows[0].model_id == "mlp"


class TestInsertWeights:
    """insert_weights — size-gated DL weight blob staging (DLE-09)."""

    def test_weight_fields_roundtrip(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Blob, declared size, fingerprint and format version persist verbatim."""
        snap = _make_snapshot(store)
        weight = _make_weight(snap.id)
        store.insert_weights([weight])
        session.commit()
        loaded = session.execute(
            select(DlWeight).where(DlWeight.snapshot_id == snap.id)
        ).scalar_one()
        assert loaded.weights_blob == b"\x89DLW-fake-tensor-data"
        assert loaded.weights_size_bytes == len(b"\x89DLW-fake-tensor-data")
        assert loaded.weights_fingerprint == "runfp123"
        assert loaded.format_version == 1

    def test_oversize_blob_rejected_before_staging(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Blob beyond 16 MiB → ValueError BEFORE add (nothing enters the session)."""
        oversize = DlWeight(
            snapshot_id=999,
            model_id="mlp",
            weights_blob=b"\x00" * 16_777_217,
            weights_size_bytes=16_777_217,
            weights_fingerprint="toobig",
            format_version=1,
        )
        with pytest.raises(ValueError, match="16777217"):
            store.insert_weights([oversize])
        staged = [obj for obj in session.new if isinstance(obj, DlWeight)]
        assert staged == []


class TestDeleteWeightsFor:
    """delete_weights_for — targeted payload cleanup primitive."""

    def test_deletes_only_targeted_snapshots_weights(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Weights of listed snapshots vanish; other snapshots' weights survive."""
        first = _make_snapshot(store, version="1")
        second = _make_snapshot(store, version="2")
        store.insert_weights([_make_weight(first.id), _make_weight(second.id)])
        session.commit()
        store.delete_weights_for([first.id])
        session.commit()
        remaining = session.execute(select(DlWeight.snapshot_id)).scalars().all()
        assert remaining == [second.id]


class TestRetireOldActive:
    """retire_old_active — status flip AND weight deletion in one tx (ADR-2)."""

    def test_retire_flips_status_and_deletes_old_weights(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Old active loses 'active' AND its dl_weights rows; keeper untouched."""
        old = _make_snapshot(store, version="1")
        store.insert_weights([_make_weight(old.id)])
        session.commit()
        new = _make_snapshot(store, version="2")
        store.insert_weights([_make_weight(new.id)])
        session.commit()
        store.retire_old_active(1, "core-3", keep_id=new.id)
        session.commit()
        retired = session.get(DlSnapshot, old.id)
        keeper = session.get(DlSnapshot, new.id)
        assert retired is not None and retired.status == "retired"
        assert keeper is not None and keeper.status == "active"
        old_weights = session.execute(
            select(func.count()).select_from(DlWeight).where(DlWeight.snapshot_id == old.id)
        ).scalar_one()
        new_weights = session.execute(
            select(func.count()).select_from(DlWeight).where(DlWeight.snapshot_id == new.id)
        ).scalar_one()
        assert int(old_weights) == 0
        assert int(new_weights) == 1

    def test_exactly_one_active_after_successive_retires(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """Chained promotions leave exactly one active per scope (DLE-12 invariant)."""
        _make_snapshot(store, version="1")
        session.commit()
        v2 = _make_snapshot(store, version="2")
        store.retire_old_active(1, "core-3", keep_id=v2.id)
        session.commit()
        v3 = _make_snapshot(store, version="3")
        store.retire_old_active(1, "core-3", keep_id=v3.id)
        session.commit()
        actives = session.execute(
            select(func.count())
            .select_from(DlSnapshot)
            .where(DlSnapshot.lottery_id == 1, DlSnapshot.model_set == "core-3")
        ).scalar_one()
        current = store.get_active(1, "core-3")
        assert int(actives) >= 1
        assert current is not None and current.id == v3.id
        statuses = session.execute(select(DlSnapshot.status).order_by(DlSnapshot.version)).all()
        assert [s for (s,) in statuses] == ["retired", "retired", "active"]

    def test_retire_with_no_other_active_is_noop(
        self, store: DlSnapshotStore, session: Session, seeded: None
    ) -> None:
        """First-ever promotion retires nothing and deletes no weights."""
        only = _make_snapshot(store, version="1")
        store.insert_weights([_make_weight(only.id)])
        session.commit()
        store.retire_old_active(1, "core-3", keep_id=only.id)
        session.commit()
        kept = session.get(DlSnapshot, only.id)
        assert kept is not None and kept.status == "active"
        assert session.execute(select(func.count()).select_from(DlWeight)).scalar_one() == 1


class TestMarkFailedRecreatePattern:
    """mark_failed — post-rollback terminal header RE-INSERT (design gotcha)."""

    def test_after_rollback_terminal_failed_row_persists(
        self,
        store: DlSnapshotStore,
        session: Session,
        db_factory: sessionmaker[Session],
        seeded: None,
    ) -> None:
        """Rollback discards the placeholder; mark_failed must re-INSERT, not update."""
        _make_snapshot(store, version="1")  # placeholder, deliberately NOT committed
        session.rollback()  # placeholder INSERT is discarded — id no longer exists
        failed = store.mark_failed(
            lottery_id=1,
            model_set="core-3",
            version="1",  # UNIQUE freed by rollback → safe reuse
            dl_generator_version="dl-test-1",
            cut=80,
            window=10,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        assert failed.status == "failed"
        assert failed.is_locked is False
        assert failed.checksum == ""
        assert failed.input_fingerprint == ""
        assert failed.cut == 80
        session.commit()
        observer = db_factory()
        try:
            rows = (
                observer.execute(
                    select(DlSnapshot).where(
                        DlSnapshot.lottery_id == 1, DlSnapshot.model_set == "core-3"
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].status == "failed"
            assert rows[0].is_locked is False
        finally:
            observer.close()
