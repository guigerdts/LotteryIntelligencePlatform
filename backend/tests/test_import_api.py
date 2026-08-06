"""PR-3 F2 import API tests (S3-06; IE-11, D-C, D-J).

Proves ``POST /draws/import`` and ``POST /draws/upload`` end-to-end through a
TestClient against the tmp migrated SQLite DB: 200 envelope summaries, 404
RESOURCE_NOT_FOUND for an unknown lottery, 409 IMPORT_CONFLICT while another run
of the same lottery is in progress, and 422 validation_error for Phase A rejects
and unknown JSON body fields. ``import_type`` is forced to ``"manual"``
server-side and never read from the client (D-C/IE-11).
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.config.settings import get_settings
from backend.app.importers.version import get_parser_version
from backend.app.models import Draw, ImportJob
from backend.app.repositories.import_repository import ImportRepository
from backend.app.services.lottery_service import LotteryService

_SUMMARY_KEYS = {
    "id",
    "status",
    "total_rows",
    "imported_rows",
    "skipped_rows",
    "duplicate_rows",
    "error_rows",
    "duration_ms",
    "checksum",
    "started_at",
    "finished_at",
}

_LOTTERY_PAYLOAD = {
    "code": "BALOTO",
    "name": "Baloto",
    "country": "CO",
    "min_number": 1,
    "max_number": 45,
    "numbers_to_select": 6,
    "super_number_min": 1,
    "super_number_max": 12,
}

_HEADERS = ["draw_number", "draw_date", "numbers", "super_number", "jackpot", "winners"]


def _row(draw_number: int) -> list[str]:
    return [str(draw_number), "2024-01-05", "1,2,3,4,5,6", "7", "5000000.00", "3"]


def _write_csv(tmp_path: Path, name: str, rows: list[list[str]]) -> Path:
    """Write a canonical-header CSV (stable bytes for checksumming)."""
    path = tmp_path / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADERS)
        writer.writerows(rows)
    return path


def _write_bad_header_csv(tmp_path: Path, name: str) -> Path:
    """Write a CSV whose header fails Phase A (unknown columns)."""
    path = tmp_path / name
    path.write_text("draw_number,draw_date\n100,2024-01-05\n", encoding="utf-8")
    return path


def _seed_lottery(db: Session, code: str = "BALOTO") -> int:
    return LotteryService(db).create({**_LOTTERY_PAYLOAD, "code": code}).id


def _seed_in_progress_run(db: Session, lottery_id: int, path: Path) -> int:
    """Insert a run stuck ``in_progress`` so a second import hits IMPORT_CONFLICT."""
    now = datetime.now(UTC)
    run = ImportRepository(db).create_run(
        {
            "lottery_id": lottery_id,
            "status": "in_progress",
            "source_file": str(path),
            "checksum": _checksum(path),
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
            "started_at": now,
            "finished_at": now,
            "last_processed_row": None,
        }
    )
    db.commit()
    return run.id


def _checksum(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_success_envelope(body: dict) -> dict:
    """Assert the Fase 0 success envelope and return the import summary."""
    assert body["success"] is True
    assert body["timestamp"]
    data = body["data"]
    assert _SUMMARY_KEYS.issubset(data.keys())
    assert data["status"] == "completed"
    return data


def _assert_error(body: dict, error_code: str) -> None:
    assert body["success"] is False
    assert body["error"]["code"] == error_code
    assert body["error"]["message"]
    assert body["timestamp"]


# --- POST /draws/upload ------------------------------------------------------


def test_upload_returns_200_with_summary_envelope(client, db: Session, tmp_path: Path) -> None:
    lottery_id = _seed_lottery(db)
    path = _write_csv(tmp_path, "up.csv", [_row(100), _row(101)])

    resp = client.post(
        "/api/v1/draws/upload",
        data={"lottery_code": "BALOTO"},
        files={"file": ("draws.csv", path.read_bytes(), "text/csv")},
    )

    assert resp.status_code == 200
    data = _assert_success_envelope(resp.json())
    assert data["total_rows"] == 2
    assert data["imported_rows"] == 2
    assert data["error_rows"] == 0

    # import_type is forced server-side to "manual" (D-C/IE-11).
    run = db.get(ImportJob, data["id"])
    assert run.import_type == "manual"
    assert run.lottery_id == lottery_id
    assert db.query(Draw).filter(Draw.lottery_id == lottery_id).count() == 2


def test_upload_unknown_lottery_returns_404(client, tmp_path: Path) -> None:
    path = _write_csv(tmp_path, "x.csv", [_row(100)])

    resp = client.post(
        "/api/v1/draws/upload",
        data={"lottery_code": "NOPE"},
        files={"file": ("draws.csv", path.read_bytes(), "text/csv")},
    )

    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_upload_phase_a_reject_returns_422_validation_error(client, db: Session) -> None:
    _seed_lottery(db)
    bad = b"draw_number,draw_date\n100,2024-01-05\n"

    resp = client.post(
        "/api/v1/draws/upload",
        data={"lottery_code": "BALOTO"},
        files={"file": ("bad.csv", bad, "text/csv")},
    )

    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")
    # Phase A reject -> one terminal rejected run, nothing imported.
    rows = db.query(ImportJob).all()
    assert len(rows) == 1
    assert rows[0].status == "rejected"
    assert not db.query(Draw).all()


def test_upload_missing_file_field_returns_422(client) -> None:
    resp = client.post("/api/v1/draws/upload", data={"lottery_code": "BALOTO"})

    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")


# --- POST /draws/import ------------------------------------------------------


def test_import_returns_200_with_summary_envelope(client, db: Session, tmp_path: Path) -> None:
    lottery_id = _seed_lottery(db)
    path = _write_csv(tmp_path, "imp.csv", [_row(100), _row(101)])

    resp = client.post(
        "/api/v1/draws/import",
        json={"lottery_code": "BALOTO", "source_file": str(path)},
    )

    assert resp.status_code == 200
    data = _assert_success_envelope(resp.json())
    assert data["imported_rows"] == 2
    run = db.get(ImportJob, data["id"])
    assert run.import_type == "manual"
    assert run.lottery_id == lottery_id


def test_import_unknown_lottery_returns_404(client, tmp_path: Path) -> None:
    path = _write_csv(tmp_path, "x.csv", [_row(100)])

    resp = client.post(
        "/api/v1/draws/import",
        json={"lottery_code": "NOPE", "source_file": str(path)},
    )

    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_import_phase_a_bad_file_returns_422(client, db: Session, tmp_path: Path) -> None:
    _seed_lottery(db)
    path = _write_bad_header_csv(tmp_path, "bad.csv")

    resp = client.post(
        "/api/v1/draws/import",
        json={"lottery_code": "BALOTO", "source_file": str(path)},
    )

    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")
    assert not db.query(Draw).all()


def test_import_extra_body_field_rejected_422(client, db: Session, tmp_path: Path) -> None:
    """extra=\"forbid\": a client-supplied import_type is rejected, never honored."""
    _seed_lottery(db)
    path = _write_csv(tmp_path, "x.csv", [_row(100)])

    resp = client.post(
        "/api/v1/draws/import",
        json={"lottery_code": "BALOTO", "source_file": str(path), "import_type": "runner"},
    )

    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")
    assert not db.query(ImportJob).all()


def test_import_concurrent_in_progress_returns_409_import_conflict(
    client, db: Session, tmp_path: Path
) -> None:
    lottery_id = _seed_lottery(db)
    path = _write_csv(tmp_path, "x.csv", [_row(100)])
    _seed_in_progress_run(db, lottery_id, path)

    resp = client.post(
        "/api/v1/draws/import",
        json={"lottery_code": "BALOTO", "source_file": str(path)},
    )

    assert resp.status_code == 409
    _assert_error(resp.json(), "IMPORT_CONFLICT")


def test_upload_concurrent_in_progress_returns_409_import_conflict(
    client, db: Session, tmp_path: Path
) -> None:
    lottery_id = _seed_lottery(db)
    path = _write_csv(tmp_path, "x.csv", [_row(100)])
    _seed_in_progress_run(db, lottery_id, path)

    resp = client.post(
        "/api/v1/draws/upload",
        data={"lottery_code": "BALOTO"},
        files={"file": ("draws.csv", path.read_bytes(), "text/csv")},
    )

    assert resp.status_code == 409
    _assert_error(resp.json(), "IMPORT_CONFLICT")
