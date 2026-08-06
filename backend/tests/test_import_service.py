"""PR-2 import service + state machine tests (S2-07).

Covers counters reconciliation (3+0+2+1=6), resume partial→completed with no
duplicate/re-insert (D-D2), exact-same-file checksum re-import (D-H), concurrency
IMPORT_CONFLICT (D-J), terminal immutability (D-E), duplicate-of-draw never
surfaces DUPLICATE_RESOURCE (IE-04/IE-11), Phase A reject → rejected terminal,
and the recorded import_type / started_by / engine_version / parser_version.

All tests run against a throwaway SQLite file migrated by alembic head (0004);
the real database/lip.db is never touched.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from alembic import command
from backend.app.config.settings import get_settings
from backend.app.core.db import build_engine
from backend.app.importers.version import get_parser_version
from backend.app.models import Draw, ImportJob, Lottery
from backend.app.repositories.import_repository import ImportRepository
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import ImportConflictError, ValidationError
from backend.app.services.import_service import ImportService
from backend.app.services.lottery_service import LotteryService

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# Baloto-like rule set (numbers_to_select=6, 1..45, super 1..12), matching the
# shared PR-1 fixtures so a csv fixture is consistent.
_DRAW_NUMS = "1,2,3,4,5,6"
_SUPER = "7"
_JACKPOT = "5000000.00"
_WINNERS = "3"


@pytest.fixture
def migrated_db(tmp_path: Path) -> Path:
    """A tmp SQLite file with the full schema (head = 0004) applied."""
    db = tmp_path / "import_service.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    return db


@pytest.fixture
def db(migrated_db: Path):
    """DI-style session over the tmp migrated DB (SQLite FK PRAGMA wired)."""
    eng = build_engine(f"sqlite:///{migrated_db}")
    factory = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    eng.dispose()


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    """Write a CSV plus a trailing newline such that the checksum is stable."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


HEADERS = ["draw_number", "draw_date", "numbers", "super_number", "jackpot", "winners"]


def _row(draw_number: int, draw_date: str, super_num: int = 7) -> list[str]:
    return [str(draw_number), draw_date, _DRAW_NUMS, str(super_num), _JACKPOT, _WINNERS]


def _seed_lottery(db) -> Lottery:
    lottery = LotteryService(db).create(
        {
            "code": "BALOTO",
            "name": "Baloto",
            "country": "CO",
            "min_number": 1,
            "max_number": 45,
            "numbers_to_select": 6,
            "super_number_min": 1,
            "super_number_max": 12,
        }
    )
    db.commit()
    return lottery


def _seed_draw(db, lottery_id: int, draw_number: int) -> Draw:
    draw = DrawService(db).create_draw_bundle(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=date(2024, 1, 1),
        numbers=[1, 2, 3, 4, 5, 6],
        super_number=7,
    )
    db.commit()
    return draw


# --- counters reconcile (IE-06: 3+0+2+1=6) ---------------------------------


def test_import_counters_reconcile_3_plus_0_plus_2_plus_1(db, tmp_path: Path) -> None:
    """Six rows -> 3 imported, 0 skipped, 2 duplicate, 1 error = 6 (IE-06)."""
    lottery = _seed_lottery(db)
    # Two draws already present become duplicates when the import replays them.
    _seed_draw(db, lottery.id, 101)
    _seed_draw(db, lottery.id, 102)

    source = tmp_path / "counters.csv"
    rows = [
        _row(100, "2024-01-05"),  # imported
        _row(103, "2024-01-06"),  # imported
        _row(104, "2024-01-07"),  # imported
        _row(101, "2024-01-08"),  # duplicate (seeded)
        _row(102, "2024-01-09"),  # duplicate (seeded)
        ["500", "not-a-date", _DRAW_NUMS, _SUPER, _JACKPOT, _WINNERS],  # error
    ]
    _write_csv(source, HEADERS, rows)

    service = ImportService(db)
    summary = service.run_import(lottery_id=lottery.id, source_path=source)

    assert summary["status"] == "completed"
    assert summary["total_rows"] == 6
    assert summary["imported_rows"] == 3
    assert summary["skipped_rows"] == 0
    assert summary["duplicate_rows"] == 2
    assert summary["error_rows"] == 1
    # Reconcile: total = imported + skipped + duplicate + error.
    assert (
        summary["total_rows"]
        == summary["imported_rows"]
        + summary["skipped_rows"]
        + summary["duplicate_rows"]
        + summary["error_rows"]
    )

    # Only the 3 new draws were inserted (draw_ids 100,103,104) on top of seeds.
    drew = list(db.query(Draw).filter(Draw.lottery_id == lottery.id).all())
    assert {d.draw_number for d in drew} == {100, 101, 102, 103, 104}

    # import_errors holds the one bad row.
    errors = ImportRepository(db).get(summary["id"]).errors
    assert len(errors) == 1
    assert "not-a-date" in errors[0].raw_row or errors[0].error_code == "bad_draw_date"


def test_duplicate_seeded_draw_never_raises_duplicate_resource(db, tmp_path: Path) -> None:
    """Re-importing an existing draw counts a duplicate, never DUPLICATE_RESOURCE (IE-11)."""
    lottery = _seed_lottery(db)
    _seed_draw(db, lottery.id, 100)

    source = tmp_path / "dup.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05")])  # already imported above

    # No repository DuplicateError / envelope duplicate on import.
    summary = ImportService(db).run_import(lottery_id=lottery.id, source_path=source)
    assert summary["status"] == "completed"
    assert summary["duplicate_rows"] == 1
    assert summary["imported_rows"] == 0
    assert len(db.query(Draw).filter(Draw.draw_number == 100).all()) == 1  # not duplicated


def test_in_file_duplicate_counted_not_imported_twice(db, tmp_path: Path) -> None:
    """A draw listed twice in ONE file: first row imports, second counts duplicate (IE-04)."""
    lottery = _seed_lottery(db)
    source = tmp_path / "infl.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05"), _row(100, "2024-01-06")])

    summary = ImportService(db).run_import(lottery_id=lottery.id, source_path=source)
    assert summary["status"] == "completed"
    assert summary["imported_rows"] == 1
    assert summary["duplicate_rows"] == 1
    # The natural key ensures only one draw row exists.
    assert len(db.query(Draw).filter(Draw.draw_number == 100).all()) == 1


def test_repository_conditional_transition_backstop(db, tmp_path: Path) -> None:
    """transition() with a stale from_status returns False (rowcount guard, D-E)."""
    lottery = _seed_lottery(db)
    source = tmp_path / "backstop.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05")])

    repo = ImportRepository(db)
    run = repo.create_run(
        {
            "lottery_id": lottery.id,
            "status": "in_progress",
            "source_file": str(source),
            "checksum": _checksum(source),
            "import_type": "manual",
            "started_by": None,
            "engine_version": get_settings().app_version,
            "parser_version": get_parser_version(),
            "total_rows": 0,
            "imported_rows": 0,
            "skipped_rows": 0,
            "duplicate_rows": 0,
            "error_rows": 0,
            "duration_ms": 0,
        }
    )
    db.commit()

    # Correct transition succeeds.
    assert repo.transition(run.id, from_status="in_progress", to_status="completed") is True
    # A stale from_status (terminal immutability) is refused at the DB rowcount.
    assert repo.transition(run.id, from_status="in_progress", to_status="partial") is False
    assert repo.transition(run.id, from_status="partial", to_status="completed") is False
    db.refresh(run)
    assert run.status == "completed"


# --- exact-same-file re-import (D-H / IE-04) --------------------------------


def test_exact_same_file_reimport_is_fresh_completed_run(db, tmp_path: Path) -> None:
    """Re-importing the identical file creates a new completed run, imported=0, dup=total."""
    lottery = _seed_lottery(db)
    source = tmp_path / "same.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05"), _row(101, "2024-01-06")])

    first = ImportService(db).run_import(lottery_id=lottery.id, source_path=source)
    second = ImportService(db).run_import(lottery_id=lottery.id, source_path=source)

    assert first["status"] == second["status"] == "completed"
    assert first["id"] != second["id"]  # a fresh imports row every execution (IE-04)
    assert second["imported_rows"] == 0
    assert second["duplicate_rows"] == second["total_rows"] == 2
    assert second["checksum"] == first["checksum"]
    assert len(db.query(Draw).filter(Draw.lottery_id == lottery.id).all()) == 2


# --- resume (D-D2 / IE-05) --------------------------------------------------


def test_resume_partial_to_completed_no_duplicate_no_reinsert(db, tmp_path: Path) -> None:
    """A partial run for the same file resumes past last_processed_row without re-counting.

    The partial run already imported the first two rows (draws 200, 201) and
    stopped; resuming the same file continues from row 3 and completes with no
    re-import of the first two rows and no duplicate counting.
    """
    lottery = _seed_lottery(db)
    # The first partial attempt committed these two draws before stopping.
    _seed_draw(db, lottery.id, 200)
    _seed_draw(db, lottery.id, 201)

    source = tmp_path / "resume.csv"
    rows = [
        _row(200, "2024-01-01"),
        _row(201, "2024-01-02"),
        _row(202, "2024-01-03"),
        _row(203, "2024-01-04"),
        _row(204, "2024-01-05"),
        _row(205, "2024-01-06"),
    ]
    _write_csv(source, HEADERS, rows)

    # Create the partial run: first two data rows (CSV rows 2,3) already done.
    repo = ImportRepository(db)
    partial = repo.create_run(
        {
            "lottery_id": lottery.id,
            "status": "partial",
            "source_file": str(source),
            "checksum": _checksum(source),
            "import_type": "manual",
            "started_by": None,
            "engine_version": get_settings().app_version,
            "parser_version": get_parser_version(),
            "total_rows": 2,
            "imported_rows": 2,
            "skipped_rows": 0,
            "duplicate_rows": 0,
            "error_rows": 0,
            "duration_ms": 5,
            "last_processed_row": 3,
        }
    )
    db.commit()

    service = ImportService(db)
    # Resume: same file -> the previous partial run continues, not a new one.
    summary = service.run_import(lottery_id=lottery.id, source_path=source, resume=True)

    assert summary["id"] == partial.id
    assert summary["status"] == "completed"
    # 2 already done + 4 resumed (202..205) -> 6 imported, 0 duplicates.
    assert summary["imported_rows"] == 6
    assert summary["duplicate_rows"] == 0
    drew = db.query(Draw).filter(Draw.lottery_id == lottery.id).all()
    assert len(drew) == 6
    assert {d.draw_number for d in drew} == {200, 201, 202, 203, 204, 205}


def test_resume_mismatched_checksum_starts_fresh_run(db, tmp_path: Path) -> None:
    """Resuming a run for a DIFFERENT file (checksum mismatch) creates a new run (D-D2)."""
    lottery = _seed_lottery(db)
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    _write_csv(source_a, HEADERS, [_row(100, "2024-01-05"), _row(101, "2024-01-06")])
    _write_csv(source_b, HEADERS, [_row(900, "2025-01-05")])

    repo = ImportRepository(db)
    partial_a = repo.create_run(
        {
            "lottery_id": lottery.id,
            "status": "partial",
            "source_file": str(source_a),
            "checksum": _checksum(source_a),
            "import_type": "manual",
            "started_by": None,
            "engine_version": get_settings().app_version,
            "parser_version": get_parser_version(),
            "total_rows": 2,
            "imported_rows": 2,
            "skipped_rows": 0,
            "duplicate_rows": 0,
            "error_rows": 0,
            "duration_ms": 5,
        }
    )
    db.commit()

    service = ImportService(db)
    # resume against source_b: checksum differs from partial_a -> a NEW run.
    summary = service.run_import(lottery_id=lottery.id, source_path=source_b, resume=True)

    assert summary["id"] != partial_a.id
    assert summary["status"] == "completed"
    assert summary["imported_rows"] == 1
    # The original partial run is untouched (still partial).
    db.refresh(partial_a)
    assert partial_a.status == "partial"


# --- concurrency (D-J) ------------------------------------------------------


def test_concurrent_same_lottery_in_progress_rejected_with_import_conflict(
    db, tmp_path: Path
) -> None:
    """A second import of the SAME lottery while one is in_progress -> IMPORT_CONFLICT."""
    lottery = _seed_lottery(db)
    source = tmp_path / "conc.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05")])

    # A concurrent run is left in_progress (never finished).
    ImportRepository(db).create_run(
        {
            "lottery_id": lottery.id,
            "status": "in_progress",
            "source_file": str(source),
            "checksum": _checksum(source),
            "import_type": "manual",
            "started_by": None,
            "engine_version": get_settings().app_version,
            "parser_version": get_parser_version(),
            "total_rows": 0,
            "imported_rows": 0,
            "skipped_rows": 0,
            "duplicate_rows": 0,
            "error_rows": 0,
            "duration_ms": 0,
        }
    )
    db.commit()

    with pytest.raises(ImportConflictError):
        ImportService(db).run_import(lottery_id=lottery.id, source_path=source)


def test_concurrent_different_lotteries_allowed(db, tmp_path: Path) -> None:
    """Different lotteries import concurrently without conflict (D-J)."""
    lottery_a = _seed_lottery(db)
    lottery_b = LotteryService(db).create(
        {
            "code": "LOTOB",
            "name": "Loto B",
            "country": "CO",
            "min_number": 1,
            "max_number": 40,
            "numbers_to_select": 5,
            "super_number_min": None,
            "super_number_max": None,
        }
    )
    db.commit()

    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    _write_csv(source_a, HEADERS, [_row(100, "2024-01-05")])
    _write_csv(
        source_b,
        HEADERS,
        [["1", "2024-01-05", "1,2,3,4,5", "", _JACKPOT, _WINNERS]],
    )

    # leave an in_progress run for lottery A while B imports.
    ImportRepository(db).create_run(
        {
            "lottery_id": lottery_a.id,
            "status": "in_progress",
            "source_file": str(source_a),
            "checksum": _checksum(source_a),
            "import_type": "manual",
            "started_by": None,
            "engine_version": get_settings().app_version,
            "parser_version": get_parser_version(),
            "total_rows": 0,
            "imported_rows": 0,
            "skipped_rows": 0,
            "duplicate_rows": 0,
            "error_rows": 0,
            "duration_ms": 0,
        }
    )
    db.commit()

    # Lottery B (different) imports fine, no ImportConflictError.
    summary = ImportService(db).run_import(lottery_id=lottery_b.id, source_path=source_b)
    assert summary["status"] == "completed"
    assert summary["imported_rows"] == 1


# --- terminal immutability --------------------------------------------------


def test_terminal_run_immutability_and_resume_creates_new_run(db, tmp_path: Path) -> None:
    """A completed run cannot be resumed: a new run is created, old stays completed."""
    lottery = _seed_lottery(db)
    source = tmp_path / "term.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05")])

    service = ImportService(db)
    first = service.run_import(lottery_id=lottery.id, source_path=source)
    assert first["status"] == "completed"

    # Attempting to resume the same (now completed) file must NOT reactivate it.
    second = service.run_import(lottery_id=lottery.id, source_path=source, resume=True)
    assert second["id"] != first["id"]
    assert second["imported_rows"] == 0
    assert second["duplicate_rows"] == 1
    # The original terminal run is unchanged (immutable).
    original = db.get(ImportJob, first["id"])
    assert original.status == "completed"


def test_rollback_rejected_run_terminal(db, tmp_path: Path) -> None:
    """A Phase A-structurally-bad file -> rejected terminal with 0 draws."""
    lottery = _seed_lottery(db)
    source = tmp_path / "reject.csv"
    # Wrong header (Phase A structural failure).
    _write_csv(source, ["wrong", "cols"], [["1", "2"]])

    with pytest.raises(ValidationError):
        ImportService(db).run_import(lottery_id=lottery.id, source_path=source)

    rows = db.query(ImportJob).filter(ImportJob.lottery_id == lottery.id).all()
    assert len(rows) == 1
    assert rows[0].status == "rejected"
    assert rows[0].imported_rows == 0
    assert not db.query(Draw).filter(Draw.lottery_id == lottery.id).first()


# --- recorded metadata (IE-07) ----------------------------------------------


def test_run_records_import_type_started_by_and_versions(db, tmp_path: Path) -> None:
    """import_type, started_by, engine_version and parser_version are recorded (IE-07)."""
    lottery = _seed_lottery(db)
    source = tmp_path / "meta.csv"
    _write_csv(source, HEADERS, [_row(100, "2024-01-05")])

    summary = ImportService(db).run_import(
        lottery_id=lottery.id,
        source_path=source,
        import_type="cli",
        started_by="operator",
    )
    row = db.get(ImportJob, summary["id"])
    assert row.status == "completed"
    assert row.import_type == "cli"
    assert row.started_by == "operator"
    assert row.engine_version == get_settings().app_version
    assert row.parser_version == get_parser_version()


def _checksum(path: Path) -> str:
    """SHA-256 hex of the file as written by _write_csv (streamed, matches FileAdapter)."""
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
