"""Lottery CRUD API tests (PR-4, P4-05; CD-01 CD-07).

Proves the lotteries router end-to-end via TestClient against a tmp migrated
SQLite DB: envelope shape, HTTP statuses for each create/get/update/delete path,
409 DUPLICATE_RESOURCE and REFERENTIAL_CONSTRAINT, 404 RESOURCE_NOT_FOUND, and
Pydantic 422 validation_error (bad type, missing required, invalid country
length). No business logic lives in the API layer — validated by design.
"""

from __future__ import annotations

from datetime import date

from backend.app.services.draw_service import DrawService
from backend.app.services.lottery_service import LotteryService

_VALID_PAYLOAD = {
    "code": "LOTO",
    "name": "Lotería Nacional",
    "country": "ES",
    "description": "National draw",
    "min_number": 1,
    "max_number": 49,
    "numbers_to_select": 6,
    "super_number_min": 1,
    "super_number_max": 9,
}


def _assert_success(body: dict, code: int) -> None:
    """Assert the body matches the Fase 0 success envelope."""
    assert code == 200 or code == 201
    assert body["success"] is True
    assert "data" in body
    assert body["timestamp"]


def _assert_error(body: dict, code: int, error_code: str) -> None:
    """Assert the body matches the Fase 0 error envelope."""
    assert body["success"] is False
    assert body["error"]["code"] == error_code
    assert body["error"]["message"]
    assert body["timestamp"]


# --- create ----------------------------------------------------------------


def test_create_lottery_returns_201_created_envelope(client) -> None:
    response = client.post("/api/v1/lotteries", json=_VALID_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    _assert_success(body, 201)
    assert body["data"]["code"] == "LOTO"
    assert body["data"]["name"] == "Lotería Nacional"
    assert body["data"]["super_number_min"] == 1


def test_list_lotteries_returns_success_envelope(client) -> None:
    client.post("/api/v1/lotteries", json=_VALID_PAYLOAD)

    response = client.get("/api/v1/lotteries")

    assert response.status_code == 200
    body = response.json()
    _assert_success(body, 200)
    assert isinstance(body["data"], list)
    assert body["data"][0]["code"] == "LOTO"


def test_get_lottery_by_id_returns_row(client) -> None:
    created = client.post("/api/v1/lotteries", json=_VALID_PAYLOAD).json()["data"]
    lottery_id = created["id"]

    response = client.get(f"/api/v1/lotteries/{lottery_id}")

    assert response.status_code == 200
    body = response.json()
    _assert_success(body, 200)
    assert body["data"]["id"] == lottery_id
    assert body["data"]["country"] == "ES"


def test_get_missing_lottery_returns_404_resource_not_found(client) -> None:
    response = client.get("/api/v1/lotteries/999")

    assert response.status_code == 404
    _assert_error(response.json(), 404, "RESOURCE_NOT_FOUND")


# --- update / delete -------------------------------------------------------


def test_update_lottery_returns_updated_row(client) -> None:
    created = client.post("/api/v1/lotteries", json=_VALID_PAYLOAD).json()["data"]
    lottery_id = created["id"]

    response = client.put(
        f"/api/v1/lotteries/{lottery_id}", json={"name": "Renamed", "description": None}
    )

    assert response.status_code == 200
    body = response.json()
    _assert_success(body, 200)
    assert body["data"]["name"] == "Renamed"
    assert body["data"]["code"] == "LOTO"  # natural key immutable


def test_update_missing_lottery_returns_404(client) -> None:
    response = client.put("/api/v1/lotteries/999", json={"name": "X"})

    assert response.status_code == 404
    _assert_error(response.json(), 404, "RESOURCE_NOT_FOUND")


def test_delete_lottery_returns_204_then_404(client) -> None:
    created = client.post("/api/v1/lotteries", json=_VALID_PAYLOAD).json()["data"]
    lottery_id = created["id"]

    response = client.delete(f"/api/v1/lotteries/{lottery_id}")

    assert response.status_code == 204
    assert response.content == b""
    # Follow-up read confirms the row is gone.
    assert client.get(f"/api/v1/lotteries/{lottery_id}").status_code == 404


def test_delete_missing_lottery_returns_404(client) -> None:
    response = client.delete("/api/v1/lotteries/999")

    assert response.status_code == 404
    _assert_error(response.json(), 404, "RESOURCE_NOT_FOUND")


def test_delete_lottery_with_draws_return_409_referential_constraint(client, db) -> None:
    """FK RESTRICT: a lottery referenced by a draw cannot be deleted (CD-05)."""
    lottery = LotteryService(db).create(_VALID_PAYLOAD)
    DrawService(db).create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=1,
        draw_date=date(2026, 1, 1),
        numbers=[1, 2, 3, 4, 5, 6],
    )

    response = client.delete(f"/api/v1/lotteries/{lottery.id}")

    assert response.status_code == 409
    _assert_error(response.json(), 409, "REFERENTIAL_CONSTRAINT")
    # The lottery remains.
    assert client.get(f"/api/v1/lotteries/{lottery.id}").status_code == 200


# --- duplicates & validation ------------------------------------------------


def test_create_duplicate_lottery_code_returns_409(client) -> None:
    client.post("/api/v1/lotteries", json=_VALID_PAYLOAD)

    response = client.post("/api/v1/lotteries", json=_VALID_PAYLOAD)

    assert response.status_code == 409
    _assert_error(response.json(), 409, "DUPLICATE_RESOURCE")


def test_update_to_duplicate_code_returns_409(client) -> None:
    client.post("/api/v1/lotteries", json=_VALID_PAYLOAD)
    other = dict(_VALID_PAYLOAD)
    other["code"] = "EURO"
    b = client.post("/api/v1/lotteries", json=other).json()["data"]

    # Try to move B onto A's code.
    response = client.put(f"/api/v1/lotteries/{b['id']}", json={"code": "LOTO"})

    assert response.status_code == 409
    _assert_error(response.json(), 409, "DUPLICATE_RESOURCE")


def test_create_missing_required_field_returns_422(client) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "name"}

    response = client.post("/api/v1/lotteries", json=payload)

    assert response.status_code == 422
    _assert_error(response.json(), 422, "validation_error")


def test_create_bad_type_returns_422(client) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["min_number"] = "not-an-int"

    response = client.post("/api/v1/lotteries", json=payload)

    assert response.status_code == 422
    _assert_error(response.json(), 422, "validation_error")


def test_create_invalid_country_length_returns_422(client) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["country"] = "ESP"  # ISO 3166-1 alpha-2 must be exactly 2 chars

    response = client.post("/api/v1/lotteries", json=payload)

    assert response.status_code == 422
    _assert_error(response.json(), 422, "validation_error")
