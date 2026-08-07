"""Statistics service integration tests: incremental/full, G9 determinism, G10 read-only.

Runs against a tmp SQLite DB migrated by alembic ``upgrade head`` (0005 stat_*),
reusing the house conftest fixtures (``db``). Covers tasks 2.5/2.6:

- incremental folds a delta and its checksum matches a from-scratch full rebuild
  over the same dataset (STE-06/C2);
- **G9 authoritative determinism**: two independent generations on the same
  dataset + checksum + generator_version produce byte-identical snapshots —
  asserting ALL FIVE: (1) snapshot checksum, (2) row count per ``stat_*`` table,
  (3) row-by-row content, (4) deterministic insertion order, (5) final snapshot
  hash;
- idempotency: a repeat generate returns the existing snapshot (no duplicate
  version);
- batch-fail: a failing batch marks the snapshot ``status='failed'`` — never
  ``active``/``partial`` — and a retry creates a fresh new version (design §3);
- **G10 read-only integrity**: the six core/import tables (``draw``,
  ``draw_numbers``, ``super_number``, ``datasets``, ``imports``, ``import_errors``)
  are byte-identical before and after generation; only ``stat_*`` row counts
  change.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.models import (
    Dataset,
    ImportError,
    ImportJob,
    StatAverage,
    StatFrequency,
    StatFrequencyPosition,
    StatGap,
    StatScalar,
    StatSnapshot,
)
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import GenerationError, NotFoundError
from backend.app.services.lottery_service import LotteryService
from backend.app.services.statistics_service import StatisticsService

# <repo>/backend/tests/statistics -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# The six G10 core/import tables that statistics MUST NOT touch (design §12/C3).
G10_CORE_TABLES = ["draw", "draw_numbers", "super_number", "datasets", "imports", "import_errors"]

# The five stat_* payload tables plus the header (design §2).
STAT_PAYLOAD_MODELS = [
    StatFrequency,
    StatFrequencyPosition,
    StatGap,
    StatAverage,
    StatScalar,
]


def _fresh_db(tmp_path: Path, name: str) -> Session:
    """Build an independent tmp migrated SQLite DB and return a session on it."""
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    class _Session(Session):  # pragma: no cover - thin convenience alias
        pass

    session = factory()
    session._engine = engine  # keep alive until test ends
    return session


def _seed_same_lotteries(db: Session, count: int = 11) -> int:
    """Seed one deterministic dataset; returns the lottery id."""
    lottery_id = _seed_lottery(db)
    for number in range(1, count + 1):
        _seed_draw(db, lottery_id, number, rotated=(number % 2 == 0))
    return lottery_id


# --- seeding helpers ----------------------------------------------------------


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
                "max_number": 9,
                "numbers_to_select": 4,
                "super_number_min": 1,
                "super_number_max": 3,
            }
        )
        .id
    )


def _seed_draw(db: Session, lottery_id: int, draw_number: int, *, rotated: bool = False) -> None:
    """Seed one deterministic draw (numbers shift each call) via the domain service."""
    base = [1, 2, 3, 4]
    numbers = [(number + (draw_number - 1)) % 9 or 9 for number in base]
    if rotated:
        numbers = numbers[1:] + numbers[:1]
    DrawService(db).create_draw_bundle(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=date(2024, 1, draw_number),
        numbers=numbers,
        super_number=((draw_number - 1) % 3) + 1,
        jackpot=None if draw_number % 2 == 0 else draw_number * 1000,
        winners=None if draw_number % 3 == 0 else draw_number,
    )
    db.commit()


def _seed_dataset(db: Session, lottery_id: int) -> None:
    """Insert one ``datasets`` row so G10 also snapshots the datasets table."""
    db.add(
        Dataset(
            version="ds-v1",
            description="G10 fixture",
            lottery_id=lottery_id,
            filters=None,
            generator_version="testgen-1",
            checksum=None,
            is_locked=True,
        )
    )
    db.commit()


def _seed_import_job(db: Session, lottery_id: int) -> None:
    """Insert one ``imports`` + one ``import_errors`` row so G10 covers import tables."""
    job = ImportJob(
        lottery_id=lottery_id,
        status="completed",
        source_file="g10.csv",
        checksum="c" * 64,
        import_type="manual",
        started_by="test",
        engine_version="0.1.0",
        parser_version="v1",
        total_rows=1,
        imported_rows=1,
        skipped_rows=0,
        duplicate_rows=0,
        error_rows=0,
        duration_ms=0,
    )
    db.add(job)
    db.flush()
    db.add(
        ImportError(
            import_id=job.id,
            row_number=1,
            draw_number=999,
            message="g10 fixture error",
            error_code="PHASE_B",
            raw_row="raw",
        )
    )
    db.commit()


# --- deterministic snapshot dump helpers ---------------------------------------


def _core_dump(db: Session, tables: list[str]) -> str:
    """Canonical byte dump of whole tables (ordered by rowid) for G10 comparison."""
    chunks = []
    for table in tables:
        rows = db.execute(text(f"SELECT * FROM {table} ORDER BY rowid")).all()
        chunks.append(f"== {table} ==\n" + "\n".join(repr(tuple(row)) for row in rows))
    return "\n".join(chunks)


def _core_checksum(db: Session, tables: list[str]) -> str:
    """SHA-256 over the canonical dump of the given tables."""
    return hashlib.sha256(_core_dump(db, tables).encode("utf-8")).hexdigest()


def _payload_rows_ordered(db: Session, snapshot_id: int) -> list[tuple]:
    """All ``stat_*`` payload rows ordered by rowid (physical insertion order)."""
    rows: list[tuple] = []
    for model in STAT_PAYLOAD_MODELS:
        for row in db.execute(
            select(model).where(model.snapshot_id == snapshot_id).order_by(model.snapshot_id)
        ).scalars():
            cols = []
            for col in model.__table__.columns:
                cols.append(getattr(row, col.name))
            rows.append(tuple(cols))
    return rows


def _payload_content_ordered(db: Session, snapshot_id: int) -> list[tuple]:
    """Payload rows in insertion (rowid) order, minus the FK snapshot_id column.

    Dropping ``snapshot_id``/``id`` makes the sequence comparable across two
    independent databases: the relative insertion ORDER of identical content is
    the G9 assertion #4, not the absolute rowid value.
    """
    content_rows: list[tuple] = []
    for model in STAT_PAYLOAD_MODELS:
        stmt = select(model).where(model.snapshot_id == snapshot_id).order_by(model.snapshot_id)
        for row in db.execute(stmt).scalars():
            cols = [
                getattr(row, col.name)
                for col in model.__table__.columns
                if col.name not in {"snapshot_id", "id"}
            ]
            content_rows.append(tuple(cols))
    return content_rows


def _snapshot_header_content(db: Session, snapshot_id: int) -> tuple:
    """Header content columns, excluding volatile ``id``/timestamps.

    ``created_at``/``updated_at`` are per-run instants and ``id`` is a dialect
    rowid; determinism (G9 #5) compares the semantic content — version, range,
    checksum, status, lock, counts.
    """
    header = db.get(StatSnapshot, snapshot_id)
    return tuple(
        getattr(header, col.name)
        for col in StatSnapshot.__table__.columns
        if col.name not in {"id", "created_at", "updated_at"}
    )


def _snapshot_hash(db: Session, snapshot_id: int) -> str:
    """Canonical hash over header content + payload content (final-snapshot hash, G9 #5)."""
    lines = [repr(_snapshot_header_content(db, snapshot_id))]
    lines += [repr(row) for row in _payload_content_ordered(db, snapshot_id)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# --- G9 / determinism & correctness --------------------------------------------


def test_incremental_matches_full_rebuild_checksum(db: Session) -> None:
    """Incremental fold over a delta equals a from-scratch full rebuild checksum."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 6):
        _seed_draw(db, lottery_id, number)

    service = StatisticsService(db)
    first = service.generate(lottery_id=lottery_id, scope="incremental")
    assert first.version == "1"
    assert first.draws_from == 1
    assert first.draws_to == 5

    # New draws 6..10 fold into a NEW version (STE-06).
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


def test_g9_two_independent_generations_are_byte_identical(db: Session, tmp_path: Path) -> None:
    """AUTHORITATIVE G9: two independent generations -> identical snapshots (all 5)."""
    # Two independent, identically-seeded databases — same dataset, same
    # generator_version, same lottery_id -> must produce byte-identical snapshots.
    first_db = _fresh_db(tmp_path, "g9_first")
    first_lottery = _seed_same_lotteries(first_db)
    first = StatisticsService(first_db).generate(lottery_id=first_lottery, scope="full")

    second_db = _fresh_db(tmp_path, "g9_second")
    second_lottery = _seed_same_lotteries(second_db)
    second = StatisticsService(second_db).generate(lottery_id=second_lottery, scope="full")

    # (1) checksum byte-identical.
    assert first.checksum == second.checksum
    # (2) row count per stat_* table identical.
    for model in STAT_PAYLOAD_MODELS:
        first_count = len(_rows_for(first_db, model, first.id))
        second_count = len(_rows_for(second_db, model, second.id))
        assert first_count == second_count, model.__tablename__
    # (3) row-by-row content identical (per table, sorted).
    for model in STAT_PAYLOAD_MODELS:
        first_rows = sorted(_rows_for(first_db, model, first.id))
        second_rows = sorted(_rows_for(second_db, model, second.id))
        assert first_rows == second_rows, model.__tablename__
    # (4) deterministic insertion order (same content sequence in rowid order).
    first_seq = _payload_content_ordered(first_db, first.id)
    second_seq = _payload_content_ordered(second_db, second.id)
    assert first_seq == second_seq
    # (5) final snapshot hash identical.
    assert _snapshot_hash(first_db, first.id) == _snapshot_hash(second_db, second.id)


def _rows_for(db: Session, model, snapshot_id: int) -> list[tuple]:
    """Raw column tuples for one model's payload rows of a snapshot."""
    stmt = select(model).where(model.snapshot_id == snapshot_id)
    return [
        tuple(getattr(row, col.name) for col in model.__table__.columns)
        for row in db.execute(stmt).scalars()
    ]


def test_idempotent_generate_returns_existing_no_duplicate_version(db: Session) -> None:
    """A repeat generate (no new data) returns the active snapshot; no dup version."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 5):
        _seed_draw(db, lottery_id, number)

    service = StatisticsService(db)
    first = service.generate(lottery_id=lottery_id, scope="incremental")
    again = service.generate(lottery_id=lottery_id, scope="incremental")

    assert again.id == first.id
    assert again.version == "1"
    snapshots = (
        db.execute(select(StatSnapshot).where(StatSnapshot.lottery_id == lottery_id))
        .scalars()
        .all()
    )
    assert [snap.version for snap in snapshots] == ["1"]
    assert [snap.status for snap in snapshots] == ["active"]


def test_unknown_lottery_raises_not_found(db: Session) -> None:
    """Generate for a missing lottery maps to NotFoundError (RESOURCE_NOT_FOUND)."""
    with pytest.raises(NotFoundError):
        StatisticsService(db).generate(lottery_id=9999)


def test_invalid_scope_raises_validation_error(db: Session) -> None:
    """An unsupported scope is rejected before any write."""
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 1)
    with pytest.raises(Exception) as excinfo:
        StatisticsService(db).generate(lottery_id=lottery_id, scope="bogus")
    assert getattr(excinfo.value, "code", "") == "validation_error"


# --- batch-fail policy (design §3) ---------------------------------------------


def test_batch_fail_marks_snapshot_failed_never_active_or_partial(db: Session) -> None:
    """A failing batch persists a terminal 'failed' snapshot; never active/partial."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 5):
        _seed_draw(db, lottery_id, number)

    service = StatisticsService(db)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated batch failure")

    original = service._payloads.bulk_insert
    service._payloads.bulk_insert = _boom
    try:
        with pytest.raises(GenerationError):
            service.generate(lottery_id=lottery_id, scope="incremental")
    finally:
        service._payloads.bulk_insert = original

    snapshots = (
        db.execute(select(StatSnapshot).where(StatSnapshot.lottery_id == lottery_id))
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

    service = StatisticsService(db)
    original = service._payloads.bulk_insert

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated batch failure")

    service._payloads.bulk_insert = _boom
    with pytest.raises(GenerationError):
        service.generate(lottery_id=lottery_id, scope="incremental")
    service._payloads.bulk_insert = original

    resumed = service.generate(lottery_id=lottery_id, scope="incremental")
    assert resumed.status == "active"
    assert resumed.version == "2"  # fresh version — never reuses the failed row

    all_rows = (
        db.execute(
            select(StatSnapshot)
            .where(StatSnapshot.lottery_id == lottery_id)
            .order_by(StatSnapshot.id)
        )
        .scalars()
        .all()
    )
    assert [row.status for row in all_rows] == ["failed", "active"]
    assert [row.version for row in all_rows] == ["1", "2"]


# --- G10 read-only integrity ---------------------------------------------------


def test_g10_core_tables_byte_identical_after_generation(db: Session) -> None:
    """G10: the six core/import tables are byte-identical before/after generation."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 8):
        _seed_draw(db, lottery_id, number)
    _seed_dataset(db, lottery_id)
    _seed_import_job(db, lottery_id)

    before = _core_dump(db, G10_CORE_TABLES)
    before_checksum = _core_checksum(db, G10_CORE_TABLES)
    core_before = {
        table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in G10_CORE_TABLES
    }
    stat_before = {
        table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in [
            "stat_snapshots",
            "stat_frequency",
            "stat_frequency_positions",
            "stat_gaps",
            "stat_averages",
            "stat_scalars",
        ]
    }

    StatisticsService(db).generate(lottery_id=lottery_id, scope="full")

    after = _core_dump(db, G10_CORE_TABLES)
    after_checksum = _core_checksum(db, G10_CORE_TABLES)
    assert after == before, "core/import tables must be byte-identical"
    assert after_checksum == before_checksum
    # Core/import row counts unchanged.
    for table in G10_CORE_TABLES:
        assert db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == core_before[table]
    # Only stat_* row counts changed (appeared).
    stat_tables = [
        "stat_snapshots",
        "stat_frequency",
        "stat_frequency_positions",
        "stat_gaps",
        "stat_averages",
        "stat_scalars",
    ]
    for table in stat_tables:
        assert db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() > stat_before[table]
