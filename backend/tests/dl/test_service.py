"""Tests for DlService — one atomic tx per model-set run (design DlService.train flow).

Spec refs: REQ-09/10, DLE-08/12/17, R1/R2. Design refs: success sequence (placeholder →
train mlp→lstm → fill header → bulk metrics → weights → retire_old_active → SINGLE
commit), failure sequence (rollback → recreate mark_failed → ONLY terminal failed
header), idempotent rerun via find_by_fingerprint, early F4 failure before any header,
``("dl:metrics", snapshot_id, model_id)`` response cache, deferred torch import.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.core.response_cache import clear_all_caches
from backend.app.dl.determinism import compute_metrics_checksum
from backend.app.dl.providers import DrawRow, FeatureRow
from backend.app.dl.registry import MODEL_SET_CORE_3, build_dl_registry
from backend.app.dl.snapshot_store import DlSnapshotStore
from backend.app.dl.weights import FORMAT_VERSION
from backend.app.dl.window import DL_FEATURE_ORDER
from backend.app.models.dl_metric import DlMetric
from backend.app.models.dl_snapshot import DlSnapshot
from backend.app.models.dl_weight import DlWeight

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# 30 draws numbered 1..30. frame = draws[:-1] → 29 draws; default real_cut = 29*4//5.
N_DRAWS = 30
_EXPECTED_CUT = (N_DRAWS - 1) * 4 // 5  # R2 walk-forward parity on the window frame
_MAX_WEIGHTS_SIZE = 16_777_216


# ---------------------------------------------------------------------------
# Fixtures and mock providers
# ---------------------------------------------------------------------------


@pytest.fixture
def db_factory(tmp_path: Path) -> sessionmaker[Session]:
    """Migrated SQLite DB with the full head schema (incl. dl_* tables)."""
    db = tmp_path / "dl_service_test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def session(db_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Single session from the migrated test DB."""
    s = db_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _clean_response_cache() -> Iterator[None]:
    """Isolate the module-level DL cache around every test."""
    clear_all_caches()
    yield
    clear_all_caches()


class MockDrawReader:
    """In-memory draw history provider returning a fixed ordered draw list."""

    def __init__(self, draws: list[DrawRow]) -> None:
        self._draws = draws

    def iter_draws(
        self, lottery_id: int, *, after_draw_number: int | None = None
    ) -> Iterator[DrawRow]:
        for d in self._draws:
            if after_draw_number is None or d.draw_number > after_draw_number:
                yield d


class MockFeatureProvider:
    """In-memory F4 provider; ``active_snapshot_id=None`` models a missing snapshot."""

    def __init__(self, rows: list[FeatureRow], active_snapshot_id: int | None = 1) -> None:
        self._rows = rows
        self._active_id = active_snapshot_id

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        return self._active_id

    def feature_rows(self, snapshot_id: int) -> Iterator[FeatureRow]:
        return iter(self._rows)


def _seed_lottery(session: Session, lottery_id: int = 1) -> None:
    """Insert and COMMIT a minimal lottery row so rollbacks keep the FK target."""
    session.execute(
        text(
            "INSERT INTO lottery "
            "(id, code, name, country, min_number, max_number, numbers_to_select, "
            "super_number_min, super_number_max, created_at) "
            "VALUES (:id, :code, :name, :country, :min_n, :max_n, :num_sel, 1, 3, :created_at)"
        ),
        {
            "id": lottery_id,
            "code": f"LOT{lottery_id}",
            "name": f"Lottery {lottery_id}",
            "country": "AR",
            "min_n": 1,
            "max_n": 60,
            "num_sel": 10,
            "created_at": "2026-01-01T00:00:00",
        },
    )
    session.flush()
    session.commit()


def _make_draws(n: int = N_DRAWS, seed: int = 42) -> list[DrawRow]:
    """Generate n deterministic draws with 10 numbers each in [1, 60]."""
    rng = random.Random(seed)
    return [
        DrawRow(draw_number=i, numbers=tuple(sorted(rng.sample(range(1, 61), 10))))
        for i in range(1, n + 1)
    ]


def _make_features(draws: list[DrawRow], seed: int = 7) -> list[FeatureRow]:
    """Generate deterministic F4 rows for every draw across DL_FEATURE_ORDER."""
    rng = random.Random(seed)
    return [
        FeatureRow(feature_id=fid, draw_number=d.draw_number, value=rng.random())
        for d in draws
        for fid in DL_FEATURE_ORDER
    ]


def _make_service(session: Session, draws: list[DrawRow], rows: list[FeatureRow]):
    """Build a DlService wired to the in-memory mock providers."""
    from backend.app.services.dl_service import DlService

    return DlService(session, MockDrawReader(draws), MockFeatureProvider(rows))


def _seed_old_active_with_weight(session: Session) -> DlSnapshot:
    """Commit a superseded active snapshot (v1) carrying one weight row."""
    store = DlSnapshotStore(session)
    old = store.create_snapshot(
        lottery_id=1,
        model_set=MODEL_SET_CORE_3,
        version="1",
        dl_generator_version="dl-test-0",
        checksum="old-checksum",
        input_fingerprint="old-fingerprint",
        cut=5,
        window=2,
        status="active",
        is_locked=True,
        draw_count=10,
        draws_from=1,
        draws_to=10,
    )
    session.flush()
    session.add(
        DlWeight(
            snapshot_id=old.id,
            model_id="mlp",
            weights_blob=b"stale-blob",
            weights_size_bytes=len(b"stale-blob"),
            weights_fingerprint="old-fingerprint",
            format_version=FORMAT_VERSION,
        )
    )
    session.commit()
    return old


def _count(session: Session, model: type) -> int:
    """Total row count for a mapped model."""
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


# ---------------------------------------------------------------------------
# Success transaction (task 3.1 + retirement cascade of task 2.x at service level)
# ---------------------------------------------------------------------------


class TestSuccessTransaction:
    """The single-commit discipline: header + metrics + weights + retirement."""

    def test_success_persists_one_active_snapshot_full_payload(self, session: Session) -> None:
        """One run persists exactly-one-active with filled header, Decimal metrics
        (number=0 sentinel, sorted params_json) and 2 weight rows tied to the run fp."""
        _seed_lottery(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))

        outcome = service.train(1, window=2)

        assert outcome.status == "active"
        assert outcome.error is None
        assert outcome.fingerprint != ""
        assert len(outcome.fingerprint) == 64
        int(outcome.fingerprint, 16)  # must not raise — valid hex SHA-256

        snapshots = list(session.execute(select(DlSnapshot)).scalars())
        assert len(snapshots) == 1, "exactly one snapshot row after the first run"
        header = snapshots[0]
        assert header.status == "active"
        assert header.is_locked is True
        assert header.model_set == MODEL_SET_CORE_3
        assert header.version == "1"
        assert outcome.snapshot_id == header.id
        # Header filled in place: real cut (R2 default), W, shared run fp, aggregate checksum.
        assert header.cut == _EXPECTED_CUT
        assert header.window == 2
        assert header.input_fingerprint == outcome.fingerprint
        assert header.checksum == outcome.metrics_checksum
        assert header.draw_count == N_DRAWS - 1
        assert (header.draws_from, header.draws_to) == (1, N_DRAWS - 1)

        metrics = list(
            session.execute(select(DlMetric).where(DlMetric.snapshot_id == header.id)).scalars()
        )
        registry = build_dl_registry()
        assert len(metrics) == 10, "one aggregate row per family x metric name"
        by_family: dict[str, set[str]] = {}
        for row in metrics:
            assert row.number == 0, "cross-number aggregates use the number=0 sentinel"
            assert isinstance(row.value, Decimal)
            assert row.value.as_tuple().exponent == -8, "exact Numeric(20,8) scale"
            assert row.model_version == header.dl_generator_version
            assert row.params_json == json.dumps(registry[row.model_id], sort_keys=True)
            by_family.setdefault(row.model_id, set()).add(row.metric_name)
        assert set(by_family) == {"mlp", "lstm"}, "registry order families both persisted"
        for names in by_family.values():
            assert names == {"accuracy", "precision", "recall", "f1", "roc_auc"}

        # Checksum digest covers both families under "family.metric" keys.
        expected_checksum = compute_metrics_checksum(
            {f"{m.model_id}.{m.metric_name}": m.value for m in metrics}
        )
        assert header.checksum == expected_checksum

        weights = list(
            session.execute(select(DlWeight).where(DlWeight.snapshot_id == header.id)).scalars()
        )
        assert len(weights) == 2, "one blob per family"
        assert {w.model_id for w in weights} == {"mlp", "lstm"}
        for w in weights:
            assert w.format_version == FORMAT_VERSION
            assert w.weights_fingerprint == header.input_fingerprint, "run fp threading"
            assert w.weights_size_bytes == len(w.weights_blob)
            assert 0 < w.weights_size_bytes <= _MAX_WEIGHTS_SIZE

    def test_retires_old_active_and_deletes_its_weights_in_same_commit(
        self, session: Session
    ) -> None:
        """A second run flips the old active to retired AND deletes its weight rows;
        exactly-one-active survives the commit (DLE-12/R1 at service level)."""
        _seed_lottery(session)
        old = _seed_old_active_with_weight(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))

        outcome = service.train(1, window=2)

        assert outcome.status == "active"
        session.refresh(old)
        assert old.status == "retired", "superseded active flipped in-tx"
        old_weights = session.execute(
            select(func.count()).select_from(DlWeight).where(DlWeight.snapshot_id == old.id)
        ).scalar_one()
        assert int(old_weights) == 0, "retirement cascades to the old weight rows"

        actives = list(
            session.execute(
                select(DlSnapshot).where(
                    DlSnapshot.status == "active",
                    DlSnapshot.lottery_id == 1,
                    DlSnapshot.model_set == MODEL_SET_CORE_3,
                )
            ).scalars()
        )
        assert len(actives) == 1, "exactly-one-active per (lottery_id, model_set)"
        new_header = actives[0]
        assert new_header.id == outcome.snapshot_id
        assert new_header.id != old.id
        assert new_header.version == "2", "version continues past the retired v1"

    def test_explicit_cut_overrides_walk_forward_default(self, session: Session) -> None:
        """An explicit cut is declared into the header instead of the len(frame)*4//5
        default (REQ-10 optionality, R2 override branch)."""
        _seed_lottery(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))

        outcome = service.train(1, window=2, cut=20)

        assert outcome.status == "active"
        header = session.execute(select(DlSnapshot)).scalar_one()
        assert header.cut == 20
        assert header.window == 2


# ---------------------------------------------------------------------------
# Forced failure (task 3.2)
# ---------------------------------------------------------------------------


class TestForcedFailure:
    """Engine failure mid-run leaves ONLY a terminal failed header."""

    def test_engine_failure_persists_only_terminal_failed_header(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rollback discards placeholder+partials; recreate mark_failed re-inserts a
        terminal failed header; the outcome carries its id plus the error string."""
        _seed_lottery(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))

        def _boom(*args: object, **kwargs: object) -> object:
            raise RuntimeError("engine exploded")

        monkeypatch.setattr("backend.app.dl.engine.train", _boom)
        outcome = service.train(1, window=2)

        assert outcome.status == "failed"
        assert "engine exploded" in (outcome.error or "")
        assert outcome.snapshot_id is not None, "terminal failed header id is reported"
        assert outcome.fingerprint == ""

        snapshots = list(session.execute(select(DlSnapshot)).scalars())
        assert len(snapshots) == 1, "ONLY the terminal failed row survives"
        failed = snapshots[0]
        assert failed.id == outcome.snapshot_id
        assert failed.status == "failed"
        assert failed.is_locked is False
        assert failed.checksum == ""
        assert failed.input_fingerprint == ""
        assert failed.version == "1", "UNIQUE slot freed by rollback is safely reused"
        assert _count(session, DlMetric) == 0, "no partial metric rows survive"
        assert _count(session, DlWeight) == 0, "no partial weight blobs survive"


# ---------------------------------------------------------------------------
# Idempotent rerun (task 3.3)
# ---------------------------------------------------------------------------


class TestIdempotentRerun:
    """Fingerprint hit short-circuits before any write."""

    def test_fingerprint_hit_returns_existing_without_new_writes(self, session: Session) -> None:
        """An identical rerun returns the existing snapshot metadata and persists zero
        additional rows — no duplicate version, metrics, or weights."""
        _seed_lottery(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))

        first = service.train(1, window=2)
        assert first.status == "active"
        counts_after_first = (
            _count(session, DlSnapshot),
            _count(session, DlMetric),
            _count(session, DlWeight),
        )

        second = service.train(1, window=2)

        assert second.status == "active"
        assert second.snapshot_id == first.snapshot_id
        assert second.fingerprint == first.fingerprint
        assert second.metrics_checksum == first.metrics_checksum
        counts_after_second = (
            _count(session, DlSnapshot),
            _count(session, DlMetric),
            _count(session, DlWeight),
        )
        assert counts_after_second == counts_after_first, "ZERO writes on fingerprint hit"
        versions = list(session.execute(select(DlSnapshot.version)).scalars())
        assert versions == ["1"], "no duplicate version created"


# ---------------------------------------------------------------------------
# Missing active F4 snapshot (task 3.4)
# ---------------------------------------------------------------------------


class TestMissingFeatureSnapshot:
    """No active F4 snapshot fails EARLY, before any header write."""

    def test_missing_f4_fails_before_any_header_write(self, session: Session) -> None:
        """Outcome reports failed with no snapshot_id and dl_snapshots stays empty."""
        from backend.app.services.dl_service import DlService

        _seed_lottery(session)
        service = DlService(
            session, MockDrawReader(_make_draws()), MockFeatureProvider([], active_snapshot_id=None)
        )

        outcome = service.train(1, window=2)

        assert outcome.status == "failed"
        assert outcome.snapshot_id is None
        assert "F4" in (outcome.error or "")
        assert _count(session, DlSnapshot) == 0, "no header written on the early path"
        assert _count(session, DlMetric) == 0
        assert _count(session, DlWeight) == 0


# ---------------------------------------------------------------------------
# Response cache registration (task 3.6)
# ---------------------------------------------------------------------------


class TestResponseCache:
    """Reads are cached under ("dl:metrics", snapshot_id, model_id)."""

    def test_metrics_reads_cache_keyed_by_snapshot_and_model(self, session: Session) -> None:
        """get_metrics populates the registered _DL_CACHE; floats appear only at the
        JSON edge; clear_all_caches() resets it (test-isolation contract)."""
        from backend.app.services.dl_service import _DL_CACHE

        _seed_lottery(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))
        outcome = service.train(1, window=2)
        assert outcome.snapshot_id is not None

        rows = service.get_metrics(1)
        assert len(rows) == 10
        for row in rows:
            assert isinstance(row["value"], float), "float only at the response edge"
        cached_all = _DL_CACHE.get(("dl:metrics", outcome.snapshot_id, None))
        assert cached_all is not None

        filtered = service.get_metrics(1, model_id="mlp")
        assert len(filtered) == 5
        assert {r["model_id"] for r in filtered} == {"mlp"}
        assert _DL_CACHE.get(("dl:metrics", outcome.snapshot_id, "mlp")) is not None

        clear_all_caches()
        assert len(_DL_CACHE) == 0

    def test_get_active_snapshot_read_shape(self, session: Session) -> None:
        """get_active_snapshot exposes header metadata; None before any run."""

        _seed_lottery(session)
        draws = _make_draws()
        service = _make_service(session, draws, _make_features(draws))
        assert service.get_active_snapshot(1) is None

        outcome = service.train(1, window=2)
        meta = service.get_active_snapshot(1)
        assert meta is not None
        assert meta["id"] == outcome.snapshot_id
        assert meta["status"] == "active"
        assert meta["model_set"] == MODEL_SET_CORE_3
        assert meta["cut"] == _EXPECTED_CUT


# ---------------------------------------------------------------------------
# Deferred torch import (DLE-17, task 3.5 lazy engine import)
# ---------------------------------------------------------------------------


class TestTorchDeferredImport:
    """Importing the service module must never pull torch at cold start."""

    def test_importing_dl_service_does_not_load_torch(self) -> None:
        """Fresh interpreter import of services.dl_service leaves torch unloaded."""
        code = "import sys; import backend.app.services.dl_service; print('torch' in sys.modules)"
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "False", "torch loaded at cold start (DLE-17)"
