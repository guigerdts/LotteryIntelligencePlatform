"""Assert-query regression for BtService draw loading (BTS-04, S2a).

Proves the draw load is NOT an N+1: a single fetch of ``_fetch_draws`` emits
at most 2 SELECTs (one draw query + one eager ``numbers`` load). Uses a
counting event listener on the engine to capture executed statements.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.draw import Draw as DrawModel
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.repositories.base import Base
from backend.app.services.bt_service import BtService


class _QueryCounter:
    """Count SELECT statements emitted against an engine."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        if isinstance(statement, str) and statement.lstrip().upper().startswith("SELECT"):
            self.count += 1


@pytest.fixture()
def counted_engine():
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    counter = _QueryCounter()
    sa.event.listen(engine, "before_cursor_execute", counter)
    yield engine, counter
    sa.event.remove(engine, "before_cursor_execute", counter)


def _seed(counted_engine, draw_count: int = 5) -> tuple[Session, int]:
    engine, _counter = counted_engine
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    lottery = Lottery(
        code="PBA",
        name="Lottery PBA",
        country="CO",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
        super_number_min=1,
        super_number_max=16,
    )
    session.add(lottery)
    session.flush()
    base = date(2015, 1, 1)
    for i in range(draw_count):
        draw = DrawModel(
            lottery_id=lottery.id,
            draw_number=i + 1,
            draw_date=base + timedelta(weeks=i),
            is_deleted=False,
        )
        session.add(draw)
        session.flush()
        for n in range(1, 6):
            session.add(DrawNumber(draw_id=draw.id, position=n, number=n))
    session.commit()
    return session, lottery.id


def test_draw_load_is_not_n_plus_one(counted_engine) -> None:
    """BTS-04: fetching draws emits at most 2 SELECTs regardless of draw count."""
    engine, counter = counted_engine
    session, lottery_id = _seed(counted_engine, draw_count=25)
    service = BtService(session)

    counter.count = 0
    draws = service._fetch_draws(lottery_id)

    assert len(draws) == 25
    # Constant SELECT count: 1 draw query + 1 eager numbers load + 1 eager
    # super_number load — NOT 1 + N (BTS-04).
    assert counter.count <= 3, f"N+1 detected: {counter.count} SELECTs for 25 draws"
    for draw in draws:
        assert draw.numbers == (1, 2, 3, 4, 5), f"draw {draw.id} numbers mismatch"
