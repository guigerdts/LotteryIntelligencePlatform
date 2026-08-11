"""Tests for meta API router — 4 endpoints (META-013).

Spec refs: META-013 (API endpoints), META-016 (error taxonomy).
Design refs: API Endpoints section.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.services.errors import MetaServiceError


@pytest.fixture
def app():
    """Create test app."""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


PREFIX = "/api/v1/meta"


class TestPostRankEndpoint:
    """POST /api/v1/meta/rank endpoint."""

    def test_rank_returns_200(self, client: TestClient) -> None:
        """Successful rank returns 200 with envelope."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.return_value = MagicMock(
                ranking_id=1,
                lottery_id=1,
                context_hash="abc123",
                version="1",
                status="active",
                fingerprint="fp123",
                entries=[],
            )
            resp = client.post(f"{PREFIX}/rank", json={"lottery_id": 1})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["ranking_id"] == 1

    def test_rank_returns_404_no_engine_data(self, client: TestClient) -> None:
        """META_NO_ENGINE_DATA returns 404."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.side_effect = MetaServiceError(
                MetaServiceError.META_NO_ENGINE_DATA, "No engine data"
            )
            resp = client.post(f"{PREFIX}/rank", json={"lottery_id": 999})
            assert resp.status_code == 404
            data = resp.json()
            assert data["success"] is False
            assert data["error"]["code"] == "META_NO_ENGINE_DATA"

    def test_rank_returns_422_weights_invalid(self, client: TestClient) -> None:
        """META_WEIGHTS_INVALID returns 422."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.side_effect = MetaServiceError(
                MetaServiceError.META_WEIGHTS_INVALID, "Weights sum to zero"
            )
            resp = client.post(f"{PREFIX}/rank", json={"lottery_id": 1, "weights": {"a": 0.0}})
            assert resp.status_code == 422
            data = resp.json()
            assert data["success"] is False
            assert data["error"]["code"] == "META_WEIGHTS_INVALID"


class TestGetRankingEndpoint:
    """GET /api/v1/meta/ranking endpoint."""

    def test_ranking_returns_200(self, client: TestClient) -> None:
        """Successful ranking retrieval returns 200."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.get_ranking.return_value = MagicMock(
                lottery_id=1,
                context_hash="abc123",
                rankings=[{"ranking_id": 1, "version": "1", "status": "active"}],
            )
            resp = client.get(f"{PREFIX}/ranking?lottery_id=1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_ranking_returns_404_not_found(self, client: TestClient) -> None:
        """META_RANKING_NOT_FOUND returns 404."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.get_ranking.side_effect = MetaServiceError(
                MetaServiceError.META_RANKING_NOT_FOUND, "Not found"
            )
            resp = client.get(f"{PREFIX}/ranking?lottery_id=999")
            assert resp.status_code == 404
            data = resp.json()
            assert data["success"] is False
            assert data["error"]["code"] == "META_RANKING_NOT_FOUND"


class TestPostSelectEndpoint:
    """POST /api/v1/meta/select endpoint."""

    def test_select_returns_200(self, client: TestClient) -> None:
        """Successful select returns 200 with envelope."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.select.return_value = MagicMock(
                selection_id=1,
                lottery_id=1,
                ranking_id=1,
                context_hash="abc123",
                version="1",
                status="active",
                fingerprint="fp123",
                entries=[],
            )
            resp = client.post(f"{PREFIX}/select", json={"lottery_id": 1})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["selection_id"] == 1

    def test_select_returns_422_top_k_invalid(self, client: TestClient) -> None:
        """Invalid top_k returns 422 validation_error (Pydantic schema level)."""
        resp = client.post(f"{PREFIX}/select", json={"lottery_id": 1, "top_k": 0})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "validation_error"

    def test_select_returns_422_top_k_over_20(self, client: TestClient) -> None:
        """top_k > 20 returns 422 validation_error (Pydantic schema level)."""
        resp = client.post(f"{PREFIX}/select", json={"lottery_id": 1, "top_k": 21})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "validation_error"


class TestGetSelectionEndpoint:
    """GET /api/v1/meta/selection endpoint."""

    def test_selection_returns_200(self, client: TestClient) -> None:
        """Successful selection retrieval returns 200."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.get_selection.return_value = MagicMock(
                lottery_id=1,
                context_hash="abc123",
                selections=[{"selection_id": 1, "version": "1", "status": "active"}],
            )
            resp = client.get(f"{PREFIX}/selection?lottery_id=1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_selection_returns_404_not_found(self, client: TestClient) -> None:
        """META_SELECTION_NOT_FOUND returns 404."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.get_selection.side_effect = MetaServiceError(
                MetaServiceError.META_SELECTION_NOT_FOUND, "Not found"
            )
            resp = client.get(f"{PREFIX}/selection?lottery_id=999")
            assert resp.status_code == 404
            data = resp.json()
            assert data["success"] is False
            assert data["error"]["code"] == "META_SELECTION_NOT_FOUND"


class TestEnvelopeFormat:
    """All responses must use standard envelope {success, data|error, timestamp}."""

    def test_success_envelope_has_timestamp(self, client: TestClient) -> None:
        """Success response includes timestamp."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.return_value = MagicMock(
                ranking_id=1, lottery_id=1, context_hash="h", version="1",
                status="active", fingerprint="f", entries=[],
            )
            resp = client.post(f"{PREFIX}/rank", json={"lottery_id": 1})
            data = resp.json()
            assert "timestamp" in data
            assert data["success"] is True

    def test_error_envelope_has_timestamp(self, client: TestClient) -> None:
        """Error response includes timestamp."""
        with patch("backend.app.api.v1.meta.MetaService") as MockService:
            mock_svc = MagicMock()
            MockService.return_value = mock_svc
            mock_svc.rank.side_effect = MetaServiceError(
                MetaServiceError.META_NO_ENGINE_DATA, "No data"
            )
            resp = client.post(f"{PREFIX}/rank", json={"lottery_id": 1})
            data = resp.json()
            assert "timestamp" in data
            assert data["success"] is False
