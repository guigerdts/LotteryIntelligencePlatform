"""Integration tests for the 5 assistant endpoints (F15 A-06..A-12).

Covers the envelope contract, 404/422 mapping, empty-data success, intent
routing.
"""

from __future__ import annotations

import re

import pytest

from backend.app.ai import prompts
from backend.app.ai.version import AI_GENERATOR_VERSION
from backend.app.services.exp_service import ExpService

FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _assert_success_envelope(client, resp) -> dict:
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["engine_version"] == AI_GENERATOR_VERSION
    assert FINGERPRINT_RE.match(data["fingerprint"])
    assert body["timestamp"]
    return data


def _assert_error(body: dict, error_code: str) -> None:
    assert body["success"] is False
    assert body["error"]["code"] == error_code
    assert body["error"]["message"]
    assert body["timestamp"]


@pytest.mark.parametrize("path", ["explain", "interpret"])
def test_get_success_envelope(client, generated, path) -> None:
    resp = client.get(f"/api/v1/assistant/{path}", params={"lottery_code": "PBA"})
    data = _assert_success_envelope(client, resp)
    assert "PBA" in data["text"]


@pytest.mark.parametrize(
    ("path", "empty_text"),
    [("explain", prompts.EXPLAIN_EMPTY), ("interpret", prompts.INTERPRET_EMPTY)],
)
def test_get_empty_data_success(client, seeded_lottery, path, empty_text) -> None:
    resp = client.get(f"/api/v1/assistant/{path}", params={"lottery_code": "PBA"})
    data = _assert_success_envelope(client, resp)
    assert data["text"] == empty_text


def test_explain_unknown_lottery_404(client) -> None:
    resp = client.get("/api/v1/assistant/explain", params={"lottery_code": "NOPE"})
    assert resp.status_code == 404
    _assert_error(resp.json(), "RESOURCE_NOT_FOUND")


def test_report_scoped_frequency_success(client, generated) -> None:
    resp = client.get(
        "/api/v1/assistant/report", params={"lottery_code": "PBA", "scope": "frequency"}
    )
    data = _assert_success_envelope(client, resp)
    assert "## Frecuencias" in data["text"]


def test_report_invalid_scope_422(client, generated) -> None:
    resp = client.get("/api/v1/assistant/report", params={"lottery_code": "PBA", "scope": "bogus"})
    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")


def test_summarize_unknown_experiment_404(client) -> None:
    resp = client.post("/api/v1/assistant/summarize", json={"experiment_id": 999})
    assert resp.status_code == 404
    _assert_error(resp.json(), "EXPERIMENT_NOT_FOUND")


def test_summarize_no_comparison_empty_data_success(client, db, seeded_lottery) -> None:
    exp_id = ExpService(db).create(lottery_id=seeded_lottery.id, name="S2").experiment_id
    resp = client.post("/api/v1/assistant/summarize", json={"experiment_id": exp_id})
    data = _assert_success_envelope(client, resp)
    assert data["text"] == prompts.SUMMARIZE_EMPTY


def test_summarize_less_than_two_runs_422(client) -> None:
    resp = client.post("/api/v1/assistant/summarize", json={"experiment_id": 1, "run_ids": [1]})
    assert resp.status_code == 422
    _assert_error(resp.json(), "validation_error")


def test_assist_unknown_intent_capabilities_success(client, seeded_lottery) -> None:
    resp = client.post(
        "/api/v1/assistant/assist", json={"question": "hola mundo", "lottery_code": "PBA"}
    )
    data = _assert_success_envelope(client, resp)
    assert data["text"] == prompts.CAPABILITIES_TEXT


def test_assist_routes_explain_intent(client, generated) -> None:
    resp = client.post(
        "/api/v1/assistant/assist",
        json={"question": "¿Por qué la frecuencia cambió?", "lottery_code": "PBA"},
    )
    data = _assert_success_envelope(client, resp)
    assert data["text"].startswith("Análisis")
