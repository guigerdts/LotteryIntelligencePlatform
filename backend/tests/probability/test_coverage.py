"""Coverage map tests (PM-08): COLD/NORMAL/HOT classification + cold boost."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.services.draw_service import DrawService
from backend.app.services.lottery_service import LotteryService
from backend.app.services.probability_service import ProbabilityService


def _seed(db: Session, code: str = "PBA") -> int:
    lottery_id = (
        LotteryService(db)
        .create(
            {
                "code": code,
                "name": "Primitiva BA",
                "country": "AR",
                "min_number": 1,
                "max_number": 9,
                "numbers_to_select": 4,
                "super_number_min": 1,
                "super_number_max": 3,
            }
        )
        .id
    )
    for i in range(1, 11):
        numbers = [2, 3, 4, 9] if i % 2 == 0 else [5, 6, 7, 9]
        DrawService(db).create_draw_bundle(
            lottery_id=lottery_id,
            draw_number=i,
            draw_date=date(2024, 1, i),
            numbers=numbers,
            super_number=1,
        )
    db.commit()
    return lottery_id


def test_coverage_map_classifies_cold_and_hot(db: Session) -> None:
    lottery_id = _seed(db)
    svc = ProbabilityService(db)
    cov = svc.coverage_map(lottery_id=lottery_id)
    # Number 1 never appears -> cold; number 9 appears in all 10 -> hot.
    assert cov[1] == "cold"
    assert cov[9] == "hot"
    # 2,3,4,5,6,7 appear in ~5 draws each -> normal.
    assert cov[2] == "normal"


def test_cold_boost_weights(db: Session) -> None:
    lottery_id = _seed(db)
    svc = ProbabilityService(db)
    weights = svc.cold_boost_weights(lottery_id=lottery_id, boost="2.0")
    assert weights[1] == Decimal("2.0")
    assert weights[9] == Decimal("1")
