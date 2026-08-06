"""Draw read API tests (PR-4, P4-05; CD-02 CD-05 CD-07).

Draws have NO create/update/delete endpoints in Fase 1 — the API_SPEC §4 subset
for F1 is functional reads only (list + get by id); ``/draws/latest``,
``/draws/import`` and ``/draws/upload`` are Fase 2 and not mounted (CD-07). Test
state is seeded through the domain services over the same tmp DB the app reads.
"""

from __future__ import annotations

from datetime import date

from backend.app.services.draw_service import DrawService
from backend.app.services.lottery_service import LotteryService

_LOTTERY_PAYLOAD = {
    "code": "LOTO",
    "name": "Lotería Nacional",
    "country": "ES",
    "min_number": 1,
    "max_number": 49,
    "numbers_to_select": 6,
    "super_number_min": 1,
    "super_number_max": 9,
}


def _seed_lottery(db, code: str = "LOTO", **overrides) -> int:
    payload = {**_LOTTERY_PAYLOAD, "code": code, **overrides}
    return LotteryService(db).create(payload).id


def _seed_draw(db, lottery_id: int, draw_number: int, *, super_value=None) -> int:
    return (
        DrawService(db)
        .create_draw_bundle(
            lottery_id=lottery_id,
            draw_number=draw_number,
            draw_date=date(2026, 1, draw_number % 28 + 1),
            numbers=[1, 2, 3, 4, 5, 6],
            super_number=super_value,
        )
        .id
    )


def test_get_draw_returns_nested_numbers_and_super_number(client, db) -> None:
    lottery_id = _seed_lottery(db)
    draw_id = _seed_draw(db, lottery_id, 1, super_value=7)

    response = client.get(f"/api/v1/draws/{draw_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] == draw_id
    assert data["lottery_id"] == lottery_id
    assert data["draw_number"] == 1
    assert data["numbers"] == [
        {"position": 1, "number": 1},
        {"position": 2, "number": 2},
        {"position": 3, "number": 3},
        {"position": 4, "number": 4},
        {"position": 5, "number": 5},
        {"position": 6, "number": 6},
    ]
    assert data["super_number"] == 7
    assert body["timestamp"]


def test_get_draw_without_super_number_returns_null(client, db) -> None:
    lottery_id = _seed_lottery(db)
    draw_id = _seed_draw(db, lottery_id, 1)

    body = client.get(f"/api/v1/draws/{draw_id}").json()

    assert body["data"]["super_number"] is None


def test_list_draws_returns_success_envelope(client, db) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 1)
    _seed_draw(db, lottery_id, 2)

    response = client.get("/api/v1/draws")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["data"][0]["numbers"]  # children serialized in the list too
    assert body["timestamp"]


def test_list_draws_filter_by_lottery_code(client, db) -> None:
    loto_id = _seed_lottery(db, "LOTO")
    euro_id = _seed_lottery(db, "EURO")
    _seed_draw(db, loto_id, 1)
    _seed_draw(db, euro_id, 1)

    body = client.get("/api/v1/draws", params={"lottery": "LOTO"}).json()

    assert len(body["data"]) == 1
    assert body["data"][0]["lottery_id"] == loto_id


def test_list_draws_pagination(client, db) -> None:
    lottery_id = _seed_lottery(db)
    for n in range(1, 6):
        _seed_draw(db, lottery_id, n)

    page1 = client.get("/api/v1/draws", params={"page": 1, "page_size": 2}).json()
    page3 = client.get("/api/v1/draws", params={"page": 3, "page_size": 2}).json()

    assert len(page1["data"]) == 2
    assert len(page3["data"]) == 1


def test_list_draws_date_filters(client, db) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 1)  # 2026-01-02
    _seed_draw(db, lottery_id, 2)  # 2026-01-03

    body = client.get(
        "/api/v1/draws", params={"date_from": "2026-01-03", "date_to": "2026-01-03"}
    ).json()

    assert len(body["data"]) == 1


def test_list_draws_order_asc(client, db) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 1)
    _seed_draw(db, lottery_id, 2)

    body = client.get("/api/v1/draws", params={"order": "asc"}).json()

    assert [d["draw_number"] for d in body["data"]] == [1, 2]


def test_get_missing_draw_returns_404_resource_not_found(client) -> None:
    response = client.get("/api/v1/draws/999")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert body["timestamp"]


def test_get_soft_deleted_draw_returns_410(client, db) -> None:
    """User mandate: RESOURCE_SOFT_DELETED maps to 410 Gone (design said 404)."""
    lottery_id = _seed_lottery(db)
    draw_id = _seed_draw(db, lottery_id, 1)
    DrawService(db).soft_delete(draw_id)

    response = client.get(f"/api/v1/draws/{draw_id}")

    assert response.status_code == 410
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RESOURCE_SOFT_DELETED"


def test_soft_deleted_draw_excluded_from_list(client, db) -> None:
    lottery_id = _seed_lottery(db)
    draw_id = _seed_draw(db, lottery_id, 1)
    _seed_draw(db, lottery_id, 2)
    DrawService(db).soft_delete(draw_id)

    body = client.get("/api/v1/draws").json()

    assert len(body["data"]) == 1
    assert body["data"][0]["draw_number"] == 2


def test_restore_brings_draw_back(client, db) -> None:
    lottery_id = _seed_lottery(db)
    draw_id = _seed_draw(db, lottery_id, 1, super_value=7)
    DrawService(db).soft_delete(draw_id)
    DrawService(db).restore(draw_id)

    body = client.get(f"/api/v1/draws/{draw_id}").json()

    assert body["data"]["is_deleted"] is False
    assert body["data"]["numbers"]  # children intact after restore (CD-05)


def test_invalid_date_filter_returns_422(client, db) -> None:
    _seed_lottery(db)

    response = client.get("/api/v1/draws", params={"date_from": "not-a-date"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_latest_import_upload_not_mounted_in_fase1(client) -> None:
    """Fase 2 endpoints must NOT exist in F1 (CD-07): no successful response.

    ``/draws/latest`` is not a registered route; the ``/{draw_id}`` int-typed
    route rejects the non-numeric segment with 422, and the import/upload POST
    paths have no POST route (405 Method Not Allowed) — none of them are
    functional F2 endpoints.
    """
    assert client.get("/api/v1/draws/latest").status_code in (404, 422)
    assert client.post("/api/v1/draws/import").status_code in (404, 405)
    assert client.post("/api/v1/draws/upload").status_code in (404, 405)
