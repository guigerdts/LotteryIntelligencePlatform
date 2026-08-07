"""Feature-engine API surface tests (P3-05, FES-09): POST idempotent, reads never precompute.

Runs against the tmp migrated SQLite DB (conftest ``client``/``db`` fixtures; head =
0006 ``feature_*``). Covers task P3-05 RED -> GREEN for the PR3 surface:

- ``POST /api/v1/feature-engine/generate`` is idempotent: a repeat POST returns the
  SAME snapshot (200, no duplicate version); ``scope=full`` always writes a NEW
  version and retires the prior active (FES-04);
- unknown lottery -> 404 ``RESOURCE_NOT_FOUND``; unknown body fields -> 422
  ``validation_error`` (ConfigDict(extra="forbid"));
- ``GET /api/v1/feature-engine/{code}/features``: missing snapshot -> 404
  ``SNAPSHOT_NOT_FOUND`` and NEVER auto-generates (FES-09 "reads never precompute");
  unknown lottery -> 404; a valid snapshot serves the persisted feature rows in
  deterministic ``(feature_id, draw_number)`` order with ``feature``/``last`` bounds.
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import FeatureSnapshot, FeatureValue
from backend.app.services.draw_service import DrawService
from backend.app.services.lottery_service import LotteryService

_LOTTERY_PAYLOAD = {
    "code": "PBM",
    "name": "Primitiva Misiones",
    "country": "AR",
    "min_number": 1,
    "max_number": 45,
    "numbers_to_select": 4,
    "super_number_min": 1,
    "super_number_max": 3,
}


def _seed_lottery(db: Session, code: str = "PBM") -> int:
    """Create a lottery row with the shared payload; return its id (seed)."""
    return LotteryService(db).create({**_LOTTERY_PAYLOAD, "code": code}).id


def _seed_draw(db: Session, lottery_id: int, draw_number: int, *, rotated: bool = False) -> None:
    """Seed one draw bundle with rotating numbers; commit (deterministic series)."""
    numbers = [(draw_number + offset) % 45 or 45 for offset in range(4)]
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


def _seed(db: Session, count: int = 5, code: str = "PBM") -> int:
    """Seed a lottery plus ``count`` draws; return the lottery id (seed)."""
    lottery_id = _seed_lottery(db, code=code)
    for number in range(1, count + 1):
        _seed_draw(db, lottery_id, number, rotated=(number % 2 == 0))
    return lottery_id


def _assert_error(body: dict, error_code: str) -> None:
    """Assert the standard error envelope fields for ``error_code`` (CD-07)."""
    assert body["success"] is False
    assert body["error"]["code"] == error_code
    assert body["error"]["message"]
    assert body["timestamp"]


def _snapshot_versions(db: Session, lottery_id: int) -> list[tuple[str, str]]:
    """Return ``(version, status)`` for every feature snapshot of the lottery."""
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


# --- POST /feature-engine/generate: idempotent 201/200 -----------------------


def test_post_generate_creates_snapshot_then_repeat_is_idempotent(
    client: TestClient, db: Session
) -> None:
    """First POST returns 201 with version 1; a repeat returns the SAME snapshot (200)."""
    lottery_id = _seed(db)
    payload = {"lottery_code": "PBM"}

    first = client.post("/api/v1/feature-engine/generate", json=payload)
    assert first.status_code == 201
    data = first.json()["data"]
    assert data["lottery_code"] == "PBM"
    assert data["feature_set"] == "core"
    assert data["version"] == "1"
    assert data["feature_engine_version"]
    assert data["draw_count"] == 5
    assert data["checksum"]
    assert data["incremental"] is True
    snapshot_id = data["snapshot_id"]
    assert _snapshot_versions(db, lottery_id) == [("1", "active")]

    # Idempotent: a repeat POST returns the SAME snapshot (200), no duplicate version.
    again = client.post("/api/v1/feature-engine/generate", json=payload)
    assert again.status_code == 200
    again_data = again.json()["data"]
    assert again_data["snapshot_id"] == snapshot_id
    assert again_data["version"] == "1"
    assert again_data["checksum"] == data["checksum"]
    assert _snapshot_versions(db, lottery_id) == [("1", "active")]


def test_post_generate_full_scope_creates_new_version(client: TestClient, db: Session) -> None:
    """``scope=full`` always writes a NEW version and retires the prior active."""
    lottery_id = _seed(db)
    assert (
        client.post("/api/v1/feature-engine/generate", json={"lottery_code": "PBM"}).status_code
        == 201
    )

    full = client.post(
        "/api/v1/feature-engine/generate",
        json={"lottery_code": "PBM", "scope": "full"},
    )
    assert full.status_code == 201
    assert full.json()["data"]["version"] == "2"
    assert full.json()["data"]["incremental"] is False
    assert _snapshot_versions(db, lottery_id) == [("1", "retired"), ("2", "active")]


def test_post_generate_unknown_lottery_returns_404(client) -> None:
    """An unknown lottery code maps to 404 RESOURCE_NOT_FOUND (CD-07)."""
    resp = client.post("/api/v1/feature-engine/generate", json={"lottery_code": "NOPE"})
    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_post_generate_unknown_fields_rejected_422(client) -> None:
    """Unknown body fields are rejected with 422 validation_error (extra='forbid')."""
    resp = client.post("/api/v1/feature-engine/generate", json={"lottery_code": "PBM", "bogus": 1})
    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")


# --- GET /feature-engine/{code}/features: never precompute, missing -> 404 ------


def test_get_features_missing_snapshot_404_and_no_autocreate(
    client: TestClient, db: Session
) -> None:
    """GET with no snapshot returns 404 SNAPSHOT_NOT_FOUND and NEVER auto-generates."""
    lottery_id = _seed(db)

    resp = client.get("/api/v1/feature-engine/PBM/features")
    assert resp.status_code == 404
    _assert_error(resp.json(), "SNAPSHOT_NOT_FOUND")

    # FES-09: the GET did NOT trigger generation — no feature_* row exists at all.
    assert (
        db.execute(select(FeatureSnapshot).where(FeatureSnapshot.lottery_id == lottery_id)).first()
        is None
    )
    assert db.execute(select(FeatureValue)).first() is None


def test_get_features_unknown_lottery_returns_404(client) -> None:
    """GET for an unknown lottery maps to 404 RESOURCE_NOT_FOUND (CD-07)."""
    resp = client.get("/api/v1/feature-engine/NOPE/features")
    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_get_features_serves_persisted_rows_in_deterministic_order(
    client: TestClient, db: Session
) -> None:
    """GET serves stored rows in (feature_id, draw_number) order; values exact strings."""
    _seed(db, count=5)
    assert (
        client.post("/api/v1/feature-engine/generate", json={"lottery_code": "PBM"}).status_code
        == 201
    )

    resp = client.get("/api/v1/feature-engine/PBM/features")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["checksum"]
    assert data["draw_count"] == 5
    assert data["feature_engine_version"]

    features = data["features"]
    assert features, "the active snapshot must serve persisted feature rows"

    # Deterministic (feature_id, draw_number) order on every read (FES-05).
    keys = [(row["feature_id"], row["draw_number"]) for row in features]
    assert keys == sorted(keys)
    # Every value is served as an exact Decimal string (no float in persisted values).
    assert all(row["value"].lstrip("-").replace(".", "", 1).isdigit() for row in features)
    # draw 1 = [1, 2, 3, 4] -> draw_sum == "10" (exact integer).
    draw_sum_row = next(
        row for row in features if row["feature_id"] == "draw_sum" and row["draw_number"] == 1
    )
    assert draw_sum_row["value"] == "10"


def test_get_features_feature_filter_and_last_bound(client: TestClient, db: Session) -> None:
    """``feature``/``last`` bounds filter the served rows without recomputing."""
    _seed(db, count=5)
    assert (
        client.post("/api/v1/feature-engine/generate", json={"lottery_code": "PBM"}).status_code
        == 201
    )

    # one feature_id across the 5 draws -> exactly 5 rows.
    one = client.get("/api/v1/feature-engine/PBM/features", params={"feature": "draw_sum"})
    assert one.status_code == 200
    rows = one.json()["data"]["features"]
    assert len(rows) == 5
    assert {row["feature_id"] for row in rows} == {"draw_sum"}
    # draws 1..5 numbers rotate so each draw sums: 10, 14, 18, 22, 26.
    by_draw = {row["draw_number"]: row["value"] for row in rows}
    assert by_draw == {1: "10", 2: "14", 3: "18", 4: "22", 5: "26"}

    # bounded read stays bounded: at most ``last`` rows.
    bounded = client.get("/api/v1/feature-engine/PBM/features", params={"last": 8})
    assert bounded.status_code == 200
    assert len(bounded.json()["data"]["features"]) == 8
