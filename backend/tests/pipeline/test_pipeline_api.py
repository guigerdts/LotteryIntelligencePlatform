"""R1/R3/D10 RED — POST /api/v1/pipeline/numbers endpoint contract."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_post_numbers_returns_success_envelope_with_stage_report(
    client: TestClient, db: Session, pipeline_db: int
) -> None:
    """A successful run returns the standard envelope with an ordered stage report."""
    response = client.post(
        "/api/v1/pipeline/numbers", json={"lottery_id": pipeline_db, "count": 2, "seed": 4}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["stages"][0]["name"] == "stats"
    assert len(body["data"]["stages"]) == 8
    assert [s["name"] for s in body["data"]["stages"]] == [
        "stats",
        "features",
        "ml",
        "dl",
        "bt",
        "rank",
        "select",
        "gen",
    ]
    result = body["data"]["result"]
    assert result is not None
    assert len(result["combinations"]) == 2


def test_failed_run_maps_to_502_with_stage_detail(
    client: TestClient, db: Session, pipeline_db: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed stage maps to a 502 error envelope carrying the stage detail."""
    from backend.app.services.meta_service import MetaService

    def failing(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("rank exploded")

    monkeypatch.setattr(MetaService, "rank", staticmethod(failing))

    response = client.post("/api/v1/pipeline/numbers", json={"lottery_id": pipeline_db})

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "PIPE_STAGE_FAILED"
    assert "rank" in error["message"]


def test_request_validation_rejects_missing_lottery(client: TestClient) -> None:
    """Missing lottery_id is rejected with a 422 validation error envelope."""
    response = client.post("/api/v1/pipeline/numbers", json={})
    assert response.status_code == 422
