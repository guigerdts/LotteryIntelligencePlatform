"""DL API surface gates (REQ-10/11 dl paragraphs, DLE-14): train/models/metrics.

Tests the DL router endpoints: ``POST /dl/train`` (SuccessEnvelope with
per-family result rows), ``GET /dl/models`` (404 ``SNAPSHOT_NOT_FOUND`` when no
active snapshot), ``GET /dl/metrics`` (ETag/304 per the ml house pattern) and
the dl-routes-are-limited guarantee (no ``/dl/predict``). Reads are served from
stored snapshots only — they never train (DLE-14).
"""

from __future__ import annotations

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers (mirrors tests/test_ml_pr5.py seeding)
# ---------------------------------------------------------------------------

_F4_FEATURES = [
    "consecutive_count",
    "draw_mean",
    "draw_range",
    "draw_sum",
    "low_high_ratio",
    "max_current_gap",
    "odd_even_ratio",
    "repeated_from_previous",
]


def _seed_lottery(session: Session, lottery_id: int = 1) -> None:
    """Insert a minimal lottery row."""
    session.execute(
        sa.text(
            "INSERT INTO lottery (id, code, name, country, min_number, max_number, "
            "numbers_to_select, created_at) "
            "VALUES (:id, :code, :name, :country, :min, :max, :sel, datetime('now'))"
        ),
        {
            "id": lottery_id,
            "code": f"L{lottery_id}",
            "name": f"Lot {lottery_id}",
            "country": "AR",
            "min": 1,
            "max": 50,
            "sel": 6,
        },
    )
    session.flush()


def _seed_draws(session: Session, lottery_id: int, count: int = 12) -> None:
    """Insert minimal draw rows with numbers."""
    for i in range(1, count + 1):
        session.execute(
            sa.text(
                "INSERT INTO draw (lottery_id, draw_number, draw_date, is_deleted, created_at) "
                "VALUES (:lid, :dn, :dd, 0, datetime('now'))"
            ),
            {"lid": lottery_id, "dn": i, "dd": f"2024-01-{i:02d}"},
        )
        draw_id = session.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        for n in range(1, 7):
            session.execute(
                sa.text(
                    "INSERT INTO draw_numbers (draw_id, number, position) VALUES (:did, :num, :pos)"
                ),
                {"did": draw_id, "num": n + (i % 10), "pos": n},
            )
    session.flush()


def _seed_f4_snapshot(session: Session, lottery_id: int) -> None:
    """Insert a feature snapshot + values for all 8 features across 12 draws."""
    session.execute(
        sa.text(
            "INSERT INTO feature_snapshots "
            "(lottery_id, feature_set, version, feature_engine_version, "
            "checksum, input_fingerprint, draws_from, draws_to, "
            "draw_count, status, is_locked, created_at, updated_at) "
            "VALUES (:lid, 'core', '1', '1.0.0', 'abc', 'test_fp', "
            "1, 12, 12, 'active', 1, datetime('now'), datetime('now'))"
        ),
        {"lid": lottery_id},
    )
    snap_id = session.execute(sa.text("SELECT last_insert_rowid()")).scalar()

    for draw_num in range(1, 13):
        for j, fid in enumerate(_F4_FEATURES):
            session.execute(
                sa.text(
                    "INSERT INTO feature_values "
                    "(snapshot_id, feature_id, feature_version, "
                    "draw_number, value) "
                    "VALUES (:sid, :fid, '1', :dn, :val)"
                ),
                {
                    "sid": snap_id,
                    "fid": fid,
                    "dn": draw_num,
                    "val": float(j * 0.1 + draw_num * 0.01),
                },
            )
    session.flush()


def _seed_full_lottery(db: Session) -> None:
    """Seed one lottery with draws + an active F4 snapshot and commit."""
    _seed_lottery(db)
    _seed_draws(db, 1)
    _seed_f4_snapshot(db, 1)
    db.commit()


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestDlApiTrain:
    """POST /dl/train gates."""

    def test_train_happy_path_returns_per_family_rows_and_persists_active(
        self, client: TestClient, db: Session
    ) -> None:
        """POST /dl/train returns SuccessEnvelope rows for mlp+lstm; GET /dl/models
        then reads the persisted active snapshot back (storage-only read)."""
        _seed_full_lottery(db)

        resp = client.post("/api/v1/dl/train", params={"lottery_id": 1, "window": 2})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["lottery_id"] == 1
        results = data["results"]
        assert len(results) == 2, "one row per trained family (mlp, lstm)"
        assert {r["family"] for r in results} == {"mlp", "lstm"}
        for row in results:
            assert set(row) == {
                "family",
                "status",
                "snapshot_id",
                "fingerprint",
                "metrics_checksum",
                "error",
            }
            assert row["status"] == "active"
            assert isinstance(row["snapshot_id"], int)
            assert row["error"] is None

        models_resp = client.get("/api/v1/dl/models", params={"lottery_id": 1})
        assert models_resp.status_code == 200
        snapshot = models_resp.json()["data"]
        assert snapshot["model_set"] == "core-3"
        assert snapshot["input_fingerprint"] == results[0]["fingerprint"]
        assert snapshot["checksum"] == results[0]["metrics_checksum"]

    def test_train_invalid_lottery_maps_to_404_resource_not_found(
        self, client: TestClient, db: Session
    ) -> None:
        """POST /dl/train for an unknown lottery id maps to 404 RESOURCE_NOT_FOUND."""
        body = client.post("/api/v1/dl/train", params={"lottery_id": 999})
        assert body.status_code == 404
        assert body.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


class TestDlApiModels:
    """GET /dl/models gates."""

    def test_models_missing_snapshot_maps_to_404_snapshot_not_found(
        self, client: TestClient, db: Session
    ) -> None:
        """GET /dl/models with no active DL snapshot returns 404 SNAPSHOT_NOT_FOUND
        and NEVER trains (DLE-14: reads never precompute)."""
        _seed_full_lottery(db)

        resp = client.get("/api/v1/dl/models", params={"lottery_id": 1})

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "SNAPSHOT_NOT_FOUND"

    def test_models_unknown_lottery_maps_to_404(self, client: TestClient) -> None:
        """GET /dl/models for an unknown lottery id returns 404 RESOURCE_NOT_FOUND."""
        resp = client.get("/api/v1/dl/models", params={"lottery_id": 999})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


class TestDlApiMetrics:
    """GET /dl/metrics gates."""

    def test_metrics_etag_then_304_empty_body(self, client: TestClient, db: Session) -> None:
        """A first GET returns persisted rows plus an ETag header; a matching
        If-None-Match yields 304 with an empty body (REQ-13 parity)."""
        _seed_full_lottery(db)
        train_resp = client.post("/api/v1/dl/train", params={"lottery_id": 1, "window": 2})
        assert train_resp.status_code == 200

        first = client.get("/api/v1/dl/metrics", params={"lottery_id": 1})
        assert first.status_code == 200
        etag = first.headers["ETag"]
        assert etag
        rows = first.json()["data"]
        assert len(rows) == 10, "5 aggregate metrics x 2 families"
        assert {r["model_id"] for r in rows} == {"mlp", "lstm"}
        for row in rows:
            assert isinstance(row["value"], float), "floats appear only at the JSON edge"

        cached = client.get(
            "/api/v1/dl/metrics", params={"lottery_id": 1}, headers={"If-None-Match": etag}
        )
        assert cached.status_code == 304
        assert cached.content == b"", "304 responses carry an empty body"


class TestDlRouteSurface:
    """dl routes are limited to train/models/metrics (REQ-11 scenario)."""

    def test_predict_route_does_not_exist(self, client: TestClient) -> None:
        """POST /dl/predict is not registered — no prediction/ranking/weights routes."""
        resp = client.post("/api/v1/dl/predict", params={"lottery_id": 1})
        assert resp.status_code == 404
