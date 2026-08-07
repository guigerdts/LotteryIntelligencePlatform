"""FeatureEngineService integration tests: incremental/full, GF1 determinism, atomicity, read-only.

Runs against a tmp SQLite DB migrated by alembic ``upgrade head`` (0006 feature_*),
mirroring the statistics service tests (``tests/statistics/test_statistics.py``).
Covers PR2 tasks P2-02/P2-03 (repositories), P2-04/P2-05 (orchestrator) and the
P2 leadership gates:

- full rebuild produces an ``active`` locked snapshot; a second full rebuild bumps
  the version and retires the old one (FES-04 no in-place recompute);
- incremental with new draws folds into a NEW version whose checksum matches a
  from-scratch full rebuild over the same dataset (FES-05/design §7);
- registry isolation: ``future-statistics`` feature is declared but never scheduled;
- batch-fail marks a terminal ``failed`` snapshot, never ``active``/``partial``
  (design §3), and a retry creates a fresh new version;
- read-only integrity: Core + ``stat_*`` rows are byte-identical before/after
  generation; only ``feature_*`` row counts change (FES-02).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.feature_engineering.registry import SOURCE_FUTURE_STATISTICS
from backend.app.models import FeatureSnapshot, FeatureValue
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import (
    GenerationError,
    NotFoundError,
    SnapshotNotFoundError,
    ValidationError,
)
from backend.app.services.feature_engine_service import FeatureEngineService, build_feature_registry
from backend.app.services.lottery_service import LotteryService

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

CORE_TABLES = [
    "draw",
    "draw_numbers",
    "super_number",
    "datasets",
    "imports",
    "import_errors",
    "stat_snapshots",
    "stat_frequency",
    "stat_frequency_positions",
    "stat_gaps",
    "stat_averages",
    "stat_scalars",
]


def _fresh_db(tmp_path: Path, name: str) -> Session:
    """Build an independent tmp migrated SQLite DB and return a session on it."""
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session._engine = engine  # keep alive until test ends
    return session


def _seed_lottery(db: Session, code: str = "PBA") -> int:
    """Seed one lottery via the domain service; returns its ``id``."""
    return (
        LotteryService(db)
        .create(
            {
                "code": code,
                "name": "Primitiva BA",
                "country": "AR",
                "min_number": 1,
                "max_number": 45,
                "numbers_to_select": 4,
                "super_number_min": 1,
                "super_number_max": 3,
            }
        )
        .id
    )


def _seed_draw(db: Session, lottery_id: int, draw_number: int, *, rotated: bool = False) -> None:
    """Seed one deterministic draw via the domain service."""
    numbers = [(draw_number + offset) % 45 or 45 for offset in range(4)]
    if rotated:
        numbers = numbers[1:] + numbers[:1]
    DrawService(db).create_draw_bundle(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=date(2024, 1, draw_number),
        numbers=numbers,
        super_number=None,
        jackpot=None,
        winners=None,
    )
    db.commit()


def _values_for(db: Session, snapshot_id: int) -> list[tuple]:
    """All ``feature_values`` rows for a snapshot (deterministic order)."""
    rows = db.execute(
        select(FeatureValue)
        .where(FeatureValue.snapshot_id == snapshot_id)
        .order_by(FeatureValue.feature_id, FeatureValue.draw_number)
    ).scalars()
    return [
        (row.feature_id, str(row.feature_version), row.draw_number, str(row.value)) for row in rows
    ]


def _core_dump(db: Session, tables: list[str]) -> str:
    chunks = []
    for table in tables:
        rows = db.execute(text(f"SELECT * FROM {table} ORDER BY rowid")).all()
        chunks.append(f"== {table} ==\n" + "\n".join(repr(tuple(row)) for row in rows))
    return "\n".join(chunks)


def _core_checksum(db: Session, tables: list[str]) -> str:
    import hashlib

    return hashlib.sha256(_core_dump(db, tables).encode("utf-8")).hexdigest()


# --- full / incremental (FES-04/FES-05) ---------------------------------------


def test_full_rebuild_bumps_version_and_retires_a_phothesis(db: Session) -> None:
    """A second full rebuild writes a NEW version and retires the prior active."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 6):
        _seed_draw(db, lottery_id, number)

    service = FeatureEngineService(db)
    first = service.generate(lottery_id=lottery_id, scope="full")
    assert first.version == "1"
    assert first.status == "active"
    assert first.is_locked is True

    second = service.generate(lottery_id=lottery_id, scope="full")
    assert second.version == "2"
    assert second.status == "active"
    assert first.status == "retired"


def test_incremental_folds_new_draws_and_matches_full_checksum(db: Session) -> None:
    """Incremental folds a delta into a NEW version; checksum == full rebuild."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 6):
        _seed_draw(db, lottery_id, number)

    service = FeatureEngineService(db)
    first = service.generate(lottery_id=lottery_id, scope="incremental")
    assert first.version == "1"
    assert first.draws_from == 1
    assert first.draws_to == 5

    # New draws 6..10 fold into a NEW version.
    for number in range(6, 11):
        _seed_draw(db, lottery_id, number)
    incremental = service.generate(lottery_id=lottery_id, scope="incremental")
    assert incremental.version == "2"
    assert incremental.draws_to == 10
    assert incremental.status == "active"
    assert first.status == "retired"

    # A from-scratch full rebuild over the same 10-draw dataset has the SAME checksum.
    full = service.generate(lottery_id=lottery_id, scope="full")
    assert full.version == "3"
    assert incremental.checksum == full.checksum


def test_two_independent_generations_are_byte_identical(db: Session, tmp_path: Path) -> None:
    """AUTHORITATIVE: two independent generations on identical datasets are identical."""
    first_db = _fresh_db(tmp_path, "f_first")
    first_lottery = _seed_lottery(first_db)
    for n in range(1, 8):
        _seed_draw(first_db, first_lottery, n)
    first = FeatureEngineService(first_db).generate(lottery_id=first_lottery, scope="full")

    second_db = _fresh_db(tmp_path, "f_second")
    second_lottery = _seed_lottery(second_db)
    for n in range(1, 8):
        _seed_draw(second_db, second_lottery, n)
    second = FeatureEngineService(second_db).generate(lottery_id=second_lottery, scope="full")

    assert first.checksum == second.checksum
    assert first.input_fingerprint == second.input_fingerprint
    assert _values_for(first_db, first.id) == _values_for(second_db, second.id)


# --- registry isolation (FES-08) P2-04 ----------------------------------------


def test_future_statistics_feature_declared_but_persists_nothing(db: Session) -> None:
    """A future-statistics feature is registered but produces NO persisted value."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 5):
        _seed_draw(db, lottery_id, number)

    reg = build_feature_registry()
    future_ids = {
        fid for fid, defn in reg.definitions().items() if defn.source == SOURCE_FUTURE_STATISTICS
    }
    assert future_ids, "the default registry must declare a future-statistics feature"

    service = FeatureEngineService(db, registry=reg)
    snap = service.generate(lottery_id=lottery_id, scope="full")
    persisted_feature_ids = {row[0] for row in _values_for(db, snap.id)}
    assert future_ids.isdisjoint(persisted_feature_ids)


# --- validation / errors (P2-00) ----------------------------------------------


def test_unknown_lottery_raises_not_found(db: Session) -> None:
    with pytest.raises(NotFoundError):
        FeatureEngineService(db).generate(lottery_id=9999)


def test_invalid_scope_raises_validation_error(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 1)
    with pytest.raises(ValidationError):
        FeatureEngineService(db).generate(lottery_id=lottery_id, scope="bogus")


def test_get_active_missing_snapshot_raises_snapshot_not_found(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 1)
    with pytest.raises(SnapshotNotFoundError):
        FeatureEngineService(db).get_active(lottery_id=lottery_id)


# --- batch-fail policy (design §7) --------------------------------------------


def test_batch_fail_marks_snapshot_failed_never_active_or_partial(db: Session) -> None:
    """A failing batch persists a terminal 'failed' snapshot; never active/partial."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 5):
        _seed_draw(db, lottery_id, number)

    service = FeatureEngineService(db)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated batch failure")

    original = service._values.bulk_insert
    service._values.bulk_insert = _boom
    try:
        with pytest.raises(GenerationError):
            service.generate(lottery_id=lottery_id, scope="full")
    finally:
        service._values.bulk_insert = original

    snapshots = (
        db.execute(select(FeatureSnapshot).where(FeatureSnapshot.lottery_id == lottery_id))
        .scalars()
        .all()
    )
    assert snapshots, "a failed snapshot header must be persisted"
    assert all(snap.status == "failed" for snap in snapshots)
    assert all(snap.status != "partial" for snap in snapshots)
    assert not any(snap.status == "active" for snap in snapshots)
    assert all(snap.is_locked is False for snap in snapshots)


def test_resume_after_failure_creates_fresh_new_version(db: Session) -> None:
    """A retry after a failed batch creates a fresh snapshot row (new version)."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 5):
        _seed_draw(db, lottery_id, number)

    service = FeatureEngineService(db)
    original = service._values.bulk_insert

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated batch failure")

    service._values.bulk_insert = _boom
    with pytest.raises(GenerationError):
        service.generate(lottery_id=lottery_id, scope="full")
    service._values.bulk_insert = original

    resumed = service.generate(lottery_id=lottery_id, scope="full")
    assert resumed.status == "active"
    assert resumed.version == "2"  # fresh version — never reuses the failed row

    all_rows = (
        db.execute(
            select(FeatureSnapshot)
            .where(FeatureSnapshot.lottery_id == lottery_id)
            .order_by(FeatureSnapshot.id)
        )
        .scalars()
        .all()
    )
    assert [row.status for row in all_rows] == ["failed", "active"]
    assert [row.version for row in all_rows] == ["1", "2"]


# --- read-only integrity (FES-02) --------------------------------------------


def test_core_and_stat_tables_byte_identical_after_generation(db: Session) -> None:
    """Core + stat_* tables are byte-identical after a feature generation run."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 7):
        _seed_draw(db, lottery_id, number)

    before = _core_dump(db, CORE_TABLES)
    before_checksum = _core_checksum(db, CORE_TABLES)
    core_counts = {
        table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in CORE_TABLES
    }

    FeatureEngineService(db).generate(lottery_id=lottery_id, scope="full")

    assert _core_dump(db, CORE_TABLES) == before, "core/stat_* must be byte-identical"
    assert _core_checksum(db, CORE_TABLES) == before_checksum
    for table in CORE_TABLES:
        assert db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == core_counts[table]
