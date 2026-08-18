"""Shared fixtures for the F15 assistant/scalars API tests (PBA lottery).

``seeded_lottery``/``generated`` reuse the root conftest's savepoint-based
``db``/``client`` (T-S7-02): seeds commit into the shared outer transaction
and are rolled back after each test — no leakage between tests.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.draw_service import DrawService
from backend.app.services.lottery_service import LotteryService

_LOTTERY = {
    "code": "PBA",
    "name": "Primitiva BA",
    "country": "AR",
    "min_number": 1,
    "max_number": 9,
    "numbers_to_select": 4,
    "super_number_min": 1,
    "super_number_max": 3,
}


@pytest.fixture
def seeded_lottery(db):
    return LotteryService(db).create({**_LOTTERY})


@pytest.fixture
def generated(client, db, seeded_lottery):
    """Seeded lottery + 3 draws + an active statistics snapshot (via API)."""
    for n in range(1, 4):
        DrawService(db).create_draw_bundle(
            lottery_id=seeded_lottery.id,
            draw_number=n,
            draw_date=date(2024, 1, n),
            numbers=[1, 2, 3, 4],
            super_number=1,
            jackpot=1000,
            winners=2,
        )
        db.commit()
    resp = client.post("/api/v1/statistics/generate", json={"lottery_code": "PBA"})
    assert resp.status_code == 201
    return resp.json()["data"]
