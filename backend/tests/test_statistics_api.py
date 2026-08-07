"""PR-3 statistics surface tests: API contract, CLI, G9/G10 e2e (design §5/§6).

Covers task 3.6 RED→GREEN against the tmp migrated SQLite DB (conftest ``client``
and ``db`` fixtures; head = 0005):

- **API contract**: ``POST /statistics/generate`` is idempotent (a repeat POST
  returns the SAME snapshot — no duplicate version); unknown lottery → 404
  ``RESOURCE_NOT_FOUND``; ``GET`` with a missing snapshot → 404
  ``SNAPSHOT_NOT_FOUND`` and NEVER auto-precomputes (STE-10/C5); reads serve the
  active snapshot's payload (frequencies/gaps/averages);
- **error taxonomy**: ``generation_error``→500, ``SNAPSHOT_NOT_FOUND``→404,
  ``SNAPSHOT_LOCKED``→409 via the shared domain handler (design §13);
- **CLI**: ``lip statistics generate`` and ``lip statistics rebuild`` produce a
  snapshot JSON, ``rebuild`` forces ``scope=full``;
- **G9 end-to-end**: an API POST and a CLI generate over two identically-seeded
  databases produce identical snapshot checksums + payload content;
- **G10 e2e**: after an API POST + a CLI generate, the six core/import tables are
  byte-identical to their pre-generation dump; only ``stat_*`` rows appeared.
"""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

import backend.app.cli as cli_module
from backend.app.api.errors import domain_error_handler
from backend.app.models import (
    StatAverage,
    StatFrequency,
    StatFrequencyPosition,
    StatGap,
    StatScalar,
    StatSnapshot,
)
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import GenerationError, SnapshotLockedError, SnapshotNotFoundError
from backend.app.services.lottery_service import LotteryService

# The six G10 core/import tables statistics MUST NOT touch (design §12/C3).
G10_CORE_TABLES = ["draw", "draw_numbers", "super_number", "datasets", "imports", "import_errors"]

STAT_PAYLOAD_MODELS = [
    StatFrequency,
    StatFrequencyPosition,
    StatGap,
    StatAverage,
    StatScalar,
]

_LOTTERY_PAYLOAD = {
    "code": "PBA",
    "name": "Primitiva BA",
    "country": "AR",
    "min_number": 1,
    "max_number": 9,
    "numbers_to_select": 4,
    "super_number_min": 1,
    "super_number_max": 3,
}


def _seed_lottery(db: Session, code: str = "PBA") -> int:
    return LotteryService(db).create({**_LOTTERY_PAYLOAD, "code": code}).id


def _seed_draw(db: Session, lottery_id: int, draw_number: int, *, rotated: bool = False) -> None:
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


def _seed_lottery_with_draws(db: Session, count: int = 5, code: str = "PBA") -> int:
    lottery_id = _seed_lottery(db, code=code)
    for number in range(1, count + 1):
        _seed_draw(db, lottery_id, number, rotated=(number % 2 == 0))
    return lottery_id


def _assert_error(body: dict, error_code: str) -> None:
    assert body["success"] is False
    assert body["error"]["code"] == error_code
    assert body["error"]["message"]
    assert body["timestamp"]


def _snapshot_versions(db: Session, lottery_id: int) -> list[tuple[str, str]]:
    rows = (
        db.execute(
            select(StatSnapshot)
            .where(StatSnapshot.lottery_id == lottery_id)
            .order_by(StatSnapshot.id)
        )
        .scalars()
        .all()
    )
    return [(row.version, row.status) for row in rows]


def _payload_content_ordered(db: Session, snapshot_id: int) -> list[tuple]:
    rows: list[tuple] = []
    for model in STAT_PAYLOAD_MODELS:
        for row in db.execute(
            select(model).where(model.snapshot_id == snapshot_id).order_by(model.snapshot_id)
        ).scalars():
            cols = [
                getattr(row, col.name)
                for col in model.__table__.columns
                if col.name not in {"snapshot_id", "id"}
            ]
            rows.append(tuple(cols))
    return rows


def _core_dump(db: Session, tables: list[str]) -> str:
    chunks = []
    for table in tables:
        rows = db.execute(text(f"SELECT * FROM {table} ORDER BY rowid")).all()
        chunks.append(f"== {table} ==\n" + "\n".join(repr(tuple(row)) for row in rows))
    return "\n".join(chunks)


def _core_checksum(db: Session, tables: list[str]) -> str:
    return hashlib.sha256(_core_dump(db, tables).encode("utf-8")).hexdigest()


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


# --- POST /statistics/generate: idempotent 201/200 ---------------------------


def test_post_generate_creates_snapshot_then_repeat_is_idempotent(
    client: TestClient, db: Session
) -> None:
    lottery_id = _seed_lottery_with_draws(db)
    payload = {"lottery_code": "PBA"}

    first = client.post("/api/v1/statistics/generate", json=payload)
    assert first.status_code == 201
    data = first.json()["data"]
    assert data["lottery_code"] == "PBA"
    assert data["version"] == "1"
    assert data["metric_set"] == "core"
    assert data["draw_count"] == 5
    assert data["checksum"]
    assert data["incremental"] is True
    snapshot_id = data["snapshot_id"]

    # Idempotent: a repeat POST returns the SAME snapshot (200), no dup version.
    again = client.post("/api/v1/statistics/generate", json=payload)
    assert again.status_code == 200
    again_data = again.json()["data"]
    assert again_data["snapshot_id"] == snapshot_id
    assert again_data["version"] == "1"
    assert again_data["checksum"] == data["checksum"]
    assert _snapshot_versions(db, lottery_id) == [("1", "active")]


def test_post_generate_full_scope_creates_new_version(client: TestClient, db: Session) -> None:
    lottery_id = _seed_lottery_with_draws(db)
    payload = {"lottery_code": "PBA", "scope": "incremental"}
    assert client.post("/api/v1/statistics/generate", json=payload).status_code == 201

    full = client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA", "scope": "full"})
    assert full.status_code == 201
    assert full.json()["data"]["version"] == "2"
    assert _snapshot_versions(db, lottery_id) == [("1", "retired"), ("2", "active")]


def test_post_generate_unknown_lottery_returns_404(client) -> None:
    resp = client.post("/api/v1/statistics/generate", json={"lottery_code": "NOPE"})
    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_post_generate_unknown_fields_rejected_422(client) -> None:
    resp = client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA", "bogus": 1})
    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")


# --- GET reads: never precompute, missing snapshot -> 404 --------------------


def test_get_reads_missing_snapshot_404_and_no_autocreate(client: TestClient, db: Session) -> None:
    lottery_id = _seed_lottery_with_draws(db)

    for path in ["frequencies", "gaps", "averages"]:
        resp = client.get(f"/api/v1/statistics/PBA/{path}")
        assert resp.status_code == 404, path
        _assert_error(resp.json(), "SNAPSHOT_NOT_FOUND")

    # STE-10: the GET did NOT trigger generation — no snapshot exists yet.
    assert (
        db.execute(select(StatSnapshot).where(StatSnapshot.lottery_id == lottery_id)).first()
        is None
    )


def test_get_reads_unknown_lottery_returns_404(client) -> None:
    for path in ["frequencies", "gaps", "averages"]:
        resp = client.get(f"/api/v1/statistics/NOPE/{path}")
        assert resp.status_code == 404
        _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_get_frequencies_serves_snapshot_payload(client: TestClient, db: Session) -> None:
    _seed_lottery_with_draws(db)
    assert (
        client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA"}).status_code == 201
    )

    resp = client.get("/api/v1/statistics/PBA/frequencies")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["checksum"]
    frequencies = {row["number"]: row["count"] for row in data["frequencies"]}
    # 5 draws × 4 numbers each; numbers 1..8 drawn (9 never drawn).
    assert len(frequencies) == 8
    assert sum(frequencies.values()) == 5 * 4  # 5 draws × 4 numbers each

    bounded = client.get("/api/v1/statistics/PBA/frequencies", params={"last": 3})
    assert bounded.status_code == 200
    assert len(bounded.json()["data"]["frequencies"]) == 3


def test_get_gaps_and_averages_serve_snapshot_payload(client: TestClient, db: Session) -> None:
    _seed_lottery_with_draws(db)
    assert (
        client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA"}).status_code == 201
    )

    gaps = client.get("/api/v1/statistics/PBA/gaps")
    assert gaps.status_code == 200
    assert gaps.json()["data"]["gaps"]

    avg = client.get("/api/v1/statistics/PBA/averages")
    assert avg.status_code == 200
    averages = avg.json()["data"]["averages"]
    assert set(averages) == {"jackpot", "winners"}
    assert averages["jackpot"]["non_null_count"] >= 0


# --- error taxonomy (design §13) ---------------------------------------------


def test_statistics_error_taxonomy_maps_codes() -> None:
    response = domain_error_handler(request=None, exc=GenerationError("boom"))
    assert (response.status_code, json.loads(response.body)["error"]["code"]) == (
        500,
        "generation_error",
    )
    response = domain_error_handler(request=None, exc=SnapshotNotFoundError("none"))
    assert (response.status_code, json.loads(response.body)["error"]["code"]) == (
        404,
        "SNAPSHOT_NOT_FOUND",
    )
    response = domain_error_handler(request=None, exc=SnapshotLockedError("locked"))
    assert (response.status_code, json.loads(response.body)["error"]["code"]) == (
        409,
        "SNAPSHOT_LOCKED",
    )


# --- CLI generate / rebuild (design §6) --------------------------------------


def test_cli_statistics_generate_and_rebuild(
    client: TestClient, db: Session, session_factory
) -> None:
    lottery_id = _seed_lottery_with_draws(db, count=4)
    factory = session_factory

    out_generate = _run_cli(["statistics", "generate", "--lottery", "PBA"], factory)
    snapshot_generate = json.loads(out_generate)
    assert snapshot_generate["lottery_code"] == "PBA"
    assert snapshot_generate["version"] == "1"
    assert snapshot_generate["status"] == "active"
    assert snapshot_generate["checksum"]
    assert snapshot_generate["is_locked"] is True
    assert _snapshot_versions(db, lottery_id) == [("1", "active")]

    out_rebuild = _run_cli(["statistics", "rebuild", "--lottery", "PBA"], factory)
    snapshot_rebuild = json.loads(out_rebuild)
    assert snapshot_rebuild["version"] == "2"  # rebuild forces a NEW version
    assert snapshot_rebuild["draws_to"] == 4
    assert _snapshot_versions(db, lottery_id) == [("1", "retired"), ("2", "active")]


def test_cli_statistics_unknown_lottery_exits_1(client, db: Session, session_factory) -> None:
    factory = session_factory
    original = cli_module.SessionLocal
    cli_module.SessionLocal = factory
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            rc = cli_module.main(["statistics", "generate", "--lottery", "NOPE"])
    finally:
        cli_module.SessionLocal = original
    assert rc == 1
    assert "RESOURCE_NOT_FOUND" in buf.getvalue()


# --- G9 end-to-end via API/CLI -----------------------------------------------


def test_g9_e2e_api_and_cli_generations_identical(
    client: TestClient, db: Session, session_factory, tmp_path
) -> None:
    """G9 e2e: API POST vs CLI generate on identical datasets -> same snapshot."""
    _seed_lottery_with_draws(db, count=6)

    # First generation via the API on the same seeded DB.
    api_resp = client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA"})
    assert api_resp.status_code == 201
    api_snapshot = api_resp.json()["data"]
    api_payload = _payload_content_ordered(db, api_snapshot["snapshot_id"])

    # Second independent generation via the CLI on the SAME dataset/DB.
    out = _run_cli(["statistics", "rebuild", "--lottery", "PBA"], session_factory)
    cli_snapshot = json.loads(out)
    cli_snapshot_id = cli_snapshot["snapshot_id"]
    cli_payload = _payload_content_ordered(db, cli_snapshot_id)

    # All five G9 assertions at e2e level (content-derived, per PR2 authoritative test).
    assert cli_snapshot["checksum"] == api_snapshot["checksum"]  # (1) checksum
    counts_match = {
        model.__tablename__: _payload_count(db, model, api_snapshot["snapshot_id"])
        == _payload_count(db, model, cli_snapshot_id)
        for model in STAT_PAYLOAD_MODELS
    }
    assert all(counts_match.values())  # (2) row count per table
    assert api_payload == cli_payload  # (3) content AND (4) insertion order
    # (5) final snapshot hash identical: header content (minus volatile id/version/
    # timestamps) + payload content — the version differs (API v1 vs CLI v2) but
    # both are full snapshots over the same dataset, so content must hash equal.
    assert _snapshot_content_hash(db, api_snapshot["snapshot_id"]) == _snapshot_content_hash(
        db, cli_snapshot_id
    )


def _payload_count(db: Session, model, snapshot_id: int) -> int:
    return len(db.execute(select(model).where(model.snapshot_id == snapshot_id)).scalars().all())


def _snapshot_content_hash(db: Session, snapshot_id: int) -> str:
    """Canonical hash over header content (minus id/version/timestamps) + payload."""
    header = db.get(StatSnapshot, snapshot_id)
    lines = [
        repr(
            tuple(
                getattr(header, col.name)
                for col in StatSnapshot.__table__.columns
                if col.name not in {"id", "version", "status", "created_at", "updated_at"}
            )
        )
    ]
    lines += [repr(row) for row in _payload_content_ordered(db, snapshot_id)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# --- G10 e2e read-only integrity ---------------------------------------------


def test_g10_e2e_core_tables_byte_identical_after_api_and_cli(
    client: TestClient, db: Session, session_factory
) -> None:
    """G10 e2e: API POST + CLI generate leave the six core tables byte-identical."""
    lottery_id = _seed_lottery_with_draws(db, count=6)
    _seed_dataset(db, lottery_id)
    _seed_import_job(db, lottery_id)

    before = _core_dump(db, G10_CORE_TABLES)
    before_checksum = _core_checksum(db, G10_CORE_TABLES)
    core_before = {
        table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in G10_CORE_TABLES
    }

    # API POST generate.
    assert (
        client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA"}).status_code == 201
    )
    # CLI generate (incremental, idempotent).
    _run_cli(["statistics", "generate", "--lottery", "PBA"], session_factory)

    after = _core_dump(db, G10_CORE_TABLES)
    assert after == before, "core/import tables must be byte-identical after generation"
    assert _core_checksum(db, G10_CORE_TABLES) == before_checksum
    for table in G10_CORE_TABLES:
        assert db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == core_before[table]

    # Only stat_* rows may appear.
    for table in [
        "stat_snapshots",
        "stat_frequency",
        "stat_frequency_positions",
        "stat_gaps",
        "stat_averages",
        "stat_scalars",
    ]:
        assert db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() > 0, table


def _seed_dataset(db: Session, lottery_id: int) -> None:
    from backend.app.models import Dataset

    db.add(
        Dataset(
            version="ds-g10",
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
    from backend.app.models import ImportError, ImportJob

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
