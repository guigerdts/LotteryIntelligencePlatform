"""Tests for the Generator API router — 4 endpoints (GEN-010, GEN-013).

Spec refs: GEN-010 (endpoints), GEN-013 (error taxonomy).
Design refs: API Endpoints section.

Mock-based tests verify routing + envelope + error-code mapping; integration
tests drive the real service over the migrated test DB (full generate→get flow
and idempotent responses).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.errors import GenServiceError

PREFIX = "/api/v1/gen"


@pytest.fixture
def api_client() -> TestClient:
    """TestClient without a DB override — used for mock-based endpoint tests."""
    return TestClient(create_app(), raise_server_exceptions=False)


def _mock_generation_result() -> MagicMock:
    """Service result matching the generate() contract."""
    return MagicMock(
        snapshot_id=1,
        lottery_id=1,
        selection_id=1,
        version="1",
        status="active",
        fingerprint="fp123",
        seed=42,
        count=10,
        combinations=[],
    )


class TestGenerateEndpoint:
    """POST /api/v1/gen/generate."""

    def test_generate_returns_200_with_envelope(self, api_client: TestClient) -> None:
        """Successful generate returns 200 with the standard envelope."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.generate.return_value = _mock_generation_result()
            resp = api_client.post(f"{PREFIX}/generate", json={"lottery_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["snapshot_id"] == 1
        assert data["data"]["lottery_id"] == 1
        assert "timestamp" in data

    def test_generate_passes_optional_args(self, api_client: TestClient) -> None:
        """count/seed/selection_id are forwarded to the service."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.generate.return_value = _mock_generation_result()
            api_client.post(
                f"{PREFIX}/generate",
                json={"lottery_id": 1, "count": 5, "seed": 42, "selection_id": 3},
            )
            MockService.return_value.generate.assert_called_once_with(
                lottery_id=1, count=5, seed=42, selection_id=3
            )

    def test_generate_returns_404_no_selection(self, api_client: TestClient) -> None:
        """GEN_NO_SELECTION → 404 envelope."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.generate.side_effect = GenServiceError(
                GenServiceError.GEN_NO_SELECTION, "no active selection"
            )
            resp = api_client.post(f"{PREFIX}/generate", json={"lottery_id": 999})
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "GEN_NO_SELECTION"

    def test_generate_returns_422_count_invalid(self, api_client: TestClient) -> None:
        """GEN_COUNT_INVALID → 422 envelope."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.generate.side_effect = GenServiceError(
                GenServiceError.GEN_COUNT_INVALID, "count out of range"
            )
            resp = api_client.post(f"{PREFIX}/generate", json={"lottery_id": 1, "count": 0})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "GEN_COUNT_INVALID"

    def test_generate_missing_lottery_id_returns_422(self, api_client: TestClient) -> None:
        """Missing required lottery_id → 422 validation_error."""
        resp = api_client.post(f"{PREFIX}/generate", json={})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestCombinationsEndpoint:
    """GET /api/v1/gen/combinations."""

    def test_combinations_returns_200(self, api_client: TestClient) -> None:
        """Successful read returns 200 with envelope."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.get_combinations.return_value = MagicMock(
                snapshot_id=1,
                lottery_id=1,
                combinations=[],
            )
            resp = api_client.get(f"{PREFIX}/combinations?lottery_id=1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"]["snapshot_id"] == 1

    def test_combinations_returns_404_snapshot_not_found(self, api_client: TestClient) -> None:
        """GEN_SNAPSHOT_NOT_FOUND → 404."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.get_combinations.side_effect = GenServiceError(
                GenServiceError.GEN_SNAPSHOT_NOT_FOUND, "no active snapshot"
            )
            resp = api_client.get(f"{PREFIX}/combinations?lottery_id=1")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "GEN_SNAPSHOT_NOT_FOUND"


class TestSnapshotEndpoint:
    """POST /api/v1/gen/snapshot."""

    def test_snapshot_returns_200(self, api_client: TestClient) -> None:
        """Successful transition returns 200 with envelope."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.update_snapshot.return_value = MagicMock(
                snapshot_id=1,
                lottery_id=1,
                selection_id=1,
                version="1",
                status="retired",
                fingerprint="fp123",
                created_at="2026-01-01T00:00:00Z",
            )
            resp = api_client.post(
                f"{PREFIX}/snapshot",
                json={"lottery_id": 1, "snapshot_id": 1, "status": "retired"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "retired"

    def test_snapshot_returns_409_duplicate(self, api_client: TestClient) -> None:
        """GEN_DUPLICATE_SNAPSHOT → 409."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.update_snapshot.side_effect = GenServiceError(
                GenServiceError.GEN_DUPLICATE_SNAPSHOT, "duplicate active"
            )
            resp = api_client.post(
                f"{PREFIX}/snapshot",
                json={"lottery_id": 1, "snapshot_id": 1, "status": "active"},
            )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "GEN_DUPLICATE_SNAPSHOT"

    def test_snapshot_invalid_status_returns_422(self, api_client: TestClient) -> None:
        """Invalid status literal → 422 validation_error."""
        resp = api_client.post(
            f"{PREFIX}/snapshot",
            json={"lottery_id": 1, "snapshot_id": 1, "status": "bogus"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestSnapshotsEndpoint:
    """GET /api/v1/gen/snapshots."""

    def test_snapshots_returns_200(self, api_client: TestClient) -> None:
        """Successful listing returns 200 with envelope."""
        with patch("backend.app.api.v1.gen.GenService") as MockService:
            MockService.return_value.get_snapshots.return_value = MagicMock(
                lottery_id=1,
                snapshots=[],
            )
            resp = api_client.get(f"{PREFIX}/snapshots?lottery_id=1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestIntegration:
    """Real service over the migrated test DB (shared ``client``/``db`` fixtures)."""

    def test_full_generate_to_read_flow(self, client: TestClient, db, seed_gen_data) -> None:
        """generate → combinations → snapshots → snapshot update end to end."""
        ids = seed_gen_data()
        generate_resp = client.post(f"{PREFIX}/generate", json={"lottery_id": ids["lottery_id"]})
        assert generate_resp.status_code == 200
        body = generate_resp.json()
        assert body["success"] is True
        assert len(body["data"]["combinations"]) == 10

        combos_resp = client.get(f"{PREFIX}/combinations?lottery_id={ids['lottery_id']}")
        assert combos_resp.status_code == 200
        assert len(combos_resp.json()["data"]["combinations"]) == 10

        snaps_resp = client.get(f"{PREFIX}/snapshots?lottery_id={ids['lottery_id']}")
        assert snaps_resp.status_code == 200
        assert len(snaps_resp.json()["data"]["snapshots"]) == 1

        snapshot_id = body["data"]["snapshot_id"]
        update_resp = client.post(
            f"{PREFIX}/snapshot",
            json={
                "lottery_id": ids["lottery_id"],
                "snapshot_id": snapshot_id,
                "status": "retired",
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["data"]["status"] == "retired"

    def test_generate_idempotent_over_api(self, client: TestClient, db, seed_gen_data) -> None:
        """Same request twice → same snapshot_id, no new rows."""
        ids = seed_gen_data()
        first = client.post(f"{PREFIX}/generate", json={"lottery_id": ids["lottery_id"]})
        second = client.post(f"{PREFIX}/generate", json={"lottery_id": ids["lottery_id"]})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["snapshot_id"] == second.json()["data"]["snapshot_id"]

    def test_generate_no_selection_returns_404(self, client: TestClient, db, seed_gen_data) -> None:
        """No active selection → 404 with GEN_NO_SELECTION (real service)."""
        ids = seed_gen_data(selection_status="retired")
        resp = client.post(f"{PREFIX}/generate", json={"lottery_id": ids["lottery_id"]})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "GEN_NO_SELECTION"

    def test_generate_invalid_count_returns_422(
        self, client: TestClient, db, seed_gen_data
    ) -> None:
        """count=0 → 422 with GEN_COUNT_INVALID (real service)."""
        ids = seed_gen_data()
        resp = client.post(f"{PREFIX}/generate", json={"lottery_id": ids["lottery_id"], "count": 0})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "GEN_COUNT_INVALID"
