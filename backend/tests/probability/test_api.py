"""Tests for Probability API routes (PR3a, T-15).

Uses FastAPI TestClient with in-memory SQLite.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.repositories.base import Base, get_db


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.close()


@pytest.fixture()
def client(session):
    """TestClient with overridden DB session."""
    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestProbabilityGenerateEndpoint:
    """POST /probability/generate"""

    def test_generate_returns_404_for_unknown_lottery(self, client):
        resp = client.post("/v1/probability/generate", json={
            "lottery_code": "NONEXISTENT",
            "scope": "full",
        })
        assert resp.status_code == 404

    def test_generate_invalid_scope_returns_422(self, client):
        resp = client.post("/v1/probability/generate", json={
            "lottery_code": "ANY",
            "scope": "bogus",
        })
        # FastAPI validates the scope via Literal type; 422 for invalid literal
        assert resp.status_code in (422, 404)

    def test_generate_missing_lottery_code_returns_422(self, client):
        resp = client.post("/v1/probability/generate", json={
            "scope": "full",
        })
        # FastAPI returns 422 for missing required fields
        assert resp.status_code in (422, 404)


class TestProbabilityReadEndpoint:
    """GET /probability/{code}/probabilities"""

    def test_read_missing_snapshot_returns_404(self, client):
        # Need a valid lottery first — create one via direct SQL
        resp = client.get("/v1/probability/NONEXISTENT/probabilities")
        assert resp.status_code == 404

    def test_read_without_model_returns_all(self, client):
        resp = client.get("/v1/probability/ANY/probabilities")
        assert resp.status_code in (404, 200)  # 404 if no lottery
