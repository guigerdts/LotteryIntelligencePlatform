"""EVService tests (EV-15): combinations count, ticket EV, high-EV window."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.services.draw_service import DrawService
from backend.app.services.ev_service import EVService
from backend.app.services.lottery_service import LotteryService


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
    for i in range(1, 6):
        DrawService(db).create_draw_bundle(
            lottery_id=lottery_id,
            draw_number=i,
            draw_date=date(2024, 1, i),
            numbers=[1, 2, 3, 4],
            super_number=1,
            jackpot=i * 1000,
            winners=i,
        )
    db.commit()
    return lottery_id


def test_combinations_count(db: Session) -> None:
    lottery_id = _seed(db)
    svc = EVService(db)
    # Universe 9, select 4 -> C(9, 4) = 126.
    assert svc.combinations_count(lottery_id=lottery_id) == 126


def test_estimate_ticket_ev_uses_latest_jackpot_and_avg_winners(db: Session) -> None:
    lottery_id = _seed(db)
    svc = EVService(db)
    # Latest jackpot = 5000; avg winners = (1+2+3+4+5)/5 = 3.
    # EV = (5000/3)/126 - 1 = 12.2275.
    ev = svc.estimate_ticket_ev(Decimal("1.0"), lottery_id=lottery_id)
    assert ev == Decimal("12.2275")


def test_combination_ev_static_pure(db: Session) -> None:
    ev = EVService.combination_ev(None, 5000, Decimal("1.0"), 126, 3)
    assert ev == Decimal("12.2275")


def test_is_high_ev_window(db: Session) -> None:
    lottery_id = _seed(db)
    svc = EVService(db)
    assert svc.is_high_ev_window(Decimal("1.0"), lottery_id=lottery_id) is True
    assert svc.is_high_ev_window(Decimal("100000"), lottery_id=lottery_id) is False
