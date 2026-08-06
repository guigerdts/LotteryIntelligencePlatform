"""Smoke tests: verify the app factory boots and the API returns the envelope."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_returns_success_envelope() -> None:
    """GET /api/v1/health returns a 200 success envelope with status ok."""
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"status": "ok"}
    assert body["timestamp"]


def test_version_returns_success_envelope() -> None:
    """GET /api/v1/version returns the app name and version in the envelope."""
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/version")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "version" in body["data"]
    assert "app" in body["data"]
    assert body["timestamp"]


def test_unknown_route_returns_error_envelope() -> None:
    """Unmatched routes map HTTPException onto the error envelope."""
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "http_error"
    assert body["timestamp"]
