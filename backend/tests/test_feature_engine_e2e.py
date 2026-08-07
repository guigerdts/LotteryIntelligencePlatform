"""Feature-engine E2E tests (P3-06, FES-09): CLI generate/rebuild, import never auto-generates.

Drives the ``lip feature-engine`` CLI surface against the tmp migrated SQLite DB
(conftest ``db``/``session_factory`` fixtures; head = 0006):

- ``lip feature-engine generate`` prints the snapshot header as JSON (manual-only);
- ``lip feature-engine rebuild`` forces ``scope=full`` and a NEW version — the old
  active is retired, never mutated (FES-04);
- an unknown lottery exits ``1`` with ``RESOURCE_NOT_FOUND`` on stderr (CD-07);
- an import NEVER auto-generates a feature snapshot (FES-09 "no import hooks"): after
  a completed import, ``feature_snapshots`` and ``feature_values`` are empty.
"""

from __future__ import annotations

import csv
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import backend.app.cli as cli_module
from backend.app.models import FeatureSnapshot, FeatureValue
from backend.app.services.draw_service import DrawService
from backend.app.services.import_service import ImportService
from backend.app.services.lottery_service import LotteryService

HEADERS = ["draw_number", "draw_date", "numbers", "super_number", "jackpot", "winners"]


def _seed_lottery(db: Session, code: str = "PBM") -> int:
    """Create a lottery row; return its id (E2E seed)."""
    return (
        LotteryService(db)
        .create(
            {
                "code": code,
                "name": "Primitiva Misiones",
                "country": "AR",
                "min_number": 1,
                "max_number": 45,
                "numbers_to_select": 6,
                "super_number_min": 1,
                "super_number_max": 12,
            }
        )
        .id
    )


def _seed_draw(db: Session, lottery_id: int, draw_number: int, *, rotated: bool = False) -> None:
    """Seed one draw bundle with rotating numbers; commit (E2E series seed)."""
    numbers = [(draw_number + offset) % 45 or 45 for offset in range(6)]
    if rotated:
        numbers = numbers[1:] + numbers[:1]
    DrawService(db).create_draw_bundle(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=date(2024, 2, draw_number),
        numbers=numbers,
        super_number=None,
        jackpot=None,
        winners=None,
    )
    db.commit()


def _run_cli(argv: list[str], factory: sessionmaker) -> str:
    """Run the CLI against ``factory``-bound sessions; return captured stdout."""
    original = cli_module.SessionLocal
    cli_module.SessionLocal = factory
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = cli_module.main(argv)
    finally:
        cli_module.SessionLocal = original
    assert rc == 0, f"CLI {argv} failed (rc={rc})"
    return buf.getvalue()


def _snapshot_versions(db: Session, lottery_id: int) -> list[tuple[str, str]]:
    """Return ``(version, status)`` tuples for the lottery's feature snapshots."""
    rows = (
        db.execute(
            select(FeatureSnapshot)
            .where(FeatureSnapshot.lottery_id == lottery_id)
            .order_by(FeatureSnapshot.id)
        )
        .scalars()
        .all()
    )
    return [(row.version, row.status) for row in rows]


# --- CLI generate / rebuild (P3-04, FES-09 manual-only) -----------------------


def test_cli_feature_generate_and_rebuild(db: Session, session_factory) -> None:
    """CLI generate prints snapshot JSON; rebuild forces a NEW version (active->retired)."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 5):
        _seed_draw(db, lottery_id, number, rotated=(number % 2 == 0))

    out_generate = _run_cli(["feature-engine", "generate", "--lottery", "PBM"], session_factory)
    snapshot_generate = json.loads(out_generate)
    assert snapshot_generate["lottery_code"] == "PBM"
    assert snapshot_generate["feature_set"] == "core"
    assert snapshot_generate["feature_engine_version"]
    assert snapshot_generate["version"] == "1"
    assert snapshot_generate["status"] == "active"
    assert snapshot_generate["is_locked"] is True
    assert snapshot_generate["checksum"]
    assert _snapshot_versions(db, lottery_id) == [("1", "active")]

    out_rebuild = _run_cli(["feature-engine", "rebuild", "--lottery", "PBM"], session_factory)
    snapshot_rebuild = json.loads(out_rebuild)
    assert snapshot_rebuild["version"] == "2"  # rebuild forces a NEW version
    assert snapshot_rebuild["draws_to"] == 4
    assert _snapshot_versions(db, lottery_id) == [("1", "retired"), ("2", "active")]


def test_cli_feature_scope_full_flag_creates_new_version(db: Session, session_factory) -> None:
    """Explicit ``--scope full`` always writes a NEW version (never mutates locked)."""
    lottery_id = _seed_lottery(db)
    for number in range(1, 4):
        _seed_draw(db, lottery_id, number)

    out_first = _run_cli(
        ["feature-engine", "generate", "--lottery", "PBM", "--scope", "full"], session_factory
    )
    assert json.loads(out_first)["version"] == "1"
    # an explicit ``--scope full`` ALWAYS writes a NEW version (never mutates locked).
    out_second = _run_cli(
        ["feature-engine", "generate", "--lottery", "PBM", "--scope", "full"], session_factory
    )
    assert json.loads(out_second)["version"] == "2"
    assert _snapshot_versions(db, lottery_id) == [("1", "retired"), ("2", "active")]


def test_cli_feature_unknown_lottery_exits_1(db: Session, session_factory) -> None:
    """An unknown lottery makes the CLI exit 1 with RESOURCE_NOT_FOUND on stderr."""
    original = cli_module.SessionLocal
    cli_module.SessionLocal = session_factory
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            rc = cli_module.main(["feature-engine", "generate", "--lottery", "NOPE"])
    finally:
        cli_module.SessionLocal = original
    assert rc == 1
    assert "RESOURCE_NOT_FOUND" in buf.getvalue()


# --- import never auto-generates (FES-09) -------------------------------------


def test_import_does_not_auto_generate_feature_snapshot(db: Session, tmp_path: Path) -> None:
    """A completed import ingests draws but creates NO feature_* row (FES-09)."""
    lottery_id = _seed_lottery(db)
    source = tmp_path / "import.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerow(["100", "2024-01-05", "1,2,3,4,5,6", "7", "5000000.00", "3"])

    summary = ImportService(db).run_import(lottery_id=lottery_id, source_path=source)
    assert summary["status"] == "completed"
    assert summary["imported_rows"] == 1

    # FES-09 "import never auto-generates": no snapshot header and no payload rows
    # appear without an explicit manual trigger (CLI/API).
    assert db.execute(select(FeatureSnapshot)).first() is None
    assert db.execute(select(FeatureValue)).first() is None
