"""Integration tests for ``GET /statistics/{code}/scalars`` (F15 A-11, D7).

Covers Decimal-string values, 404 codes, and no precompute (STE-10).
"""

from __future__ import annotations

from sqlalchemy import select

from backend.app.models import StatScalar, StatSnapshot


def _assert_error(body: dict, error_code: str) -> None:
    assert body["success"] is False
    assert body["error"]["code"] == error_code
    assert body["error"]["message"]
    assert body["timestamp"]


def test_get_scalars_serves_snapshot_scalars(client, db, generated) -> None:
    resp = client.get("/api/v1/statistics/PBA/scalars")
    assert resp.status_code == 200
    data = resp.json()["data"]
    scalars = {row["name"]: row["value"] for row in data["scalars"]}
    assert "entropy" in scalars
    persisted = db.execute(
        select(StatScalar).where(StatScalar.snapshot_id == generated["snapshot_id"])
    ).scalars()
    assert scalars == {row.name: f"{row.value.normalize():f}" for row in persisted}


def test_get_scalars_unknown_lottery_404(client) -> None:
    resp = client.get("/api/v1/statistics/NOPE/scalars")
    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_get_scalars_missing_snapshot_404_and_no_precompute(client, db, seeded_lottery) -> None:
    resp = client.get("/api/v1/statistics/PBA/scalars")
    assert resp.status_code == 404
    _assert_error(resp.json(), "SNAPSHOT_NOT_FOUND")
    assert (
        db.execute(select(StatSnapshot).where(StatSnapshot.lottery_id == seeded_lottery.id)).first()
        is None
    )
