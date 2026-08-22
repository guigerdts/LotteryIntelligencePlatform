"""Integration tests for _DrawReaderAdapter against a real session.

Regression guard for the walkthrough finding WALK-5: the adapter used to wrap
DrawRepository, which has no iter_draws(), crashing probability generation
end-to-end while unit tests stayed green because they injected a fake provider.

These tests exercise the adapter against real ORM rows so a repository seam
mismatch can never ship silently again.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base
from backend.app.models.draw import Draw
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.services.errors import NotFoundError
from backend.app.services.probability_service import _DrawReaderAdapter


@pytest.fixture()
def session():
    """Create an in-memory SQLite session with all tables."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture()
def lottery(session):
    """Create a Baloto-like lottery."""
    lot = Lottery(
        code="BAL",
        name="Baloto",
        country="CO",
        min_number=1,
        max_number=45,
        numbers_to_select=6,
    )
    session.add(lot)
    session.commit()
    return lot


def _add_draw(session, lottery_id, draw_number, numbers):
    """Persist one draw with its main numbers (positions 1..n)."""
    draw = Draw(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=date(2024, 1, 1 + draw_number % 28),
        jackpot=None,
        winners=0,
    )
    session.add(draw)
    session.flush()
    for pos, num in enumerate(numbers, start=1):
        session.add(DrawNumber(draw_id=draw.id, position=pos, number=num))
    session.commit()
    return draw


# --- Tests ---


def test_adapter_reads_real_draws_in_order(session, lottery):
    """iter_draws streams real draws ordered by draw_number with full tuples."""
    _add_draw(session, lottery.id, 2092, [6, 7, 8, 9, 10, 11])
    _add_draw(session, lottery.id, 2091, [1, 2, 3, 4, 5, 6])

    adapter = _DrawReaderAdapter(session)
    rows = list(adapter.iter_draws(lottery.id))

    assert [r.draw_number for r in rows] == [2091, 2092]
    assert [tuple(r.numbers) for r in rows] == [(1, 2, 3, 4, 5, 6), (6, 7, 8, 9, 10, 11)]


def test_adapter_after_draw_number_filters_incrementally(session, lottery):
    """after_draw_number returns only newer draws (incremental path)."""
    _add_draw(session, lottery.id, 10, [1, 2, 3, 4, 5, 6])
    _add_draw(session, lottery.id, 11, [7, 8, 9, 10, 11, 12])

    adapter = _DrawReaderAdapter(session)
    rows = list(adapter.iter_draws(lottery.id, after_draw_number=10))

    assert [r.draw_number for r in rows] == [11]


def test_adapter_lottery_rules_from_same_session(session, lottery):
    """lottery_rules resolves through the same wrapped repository session."""
    adapter = _DrawReaderAdapter(session)
    rules = adapter.lottery_rules(lottery.id)

    assert (rules.min_number, rules.max_number) == (1, 45)
    assert rules.numbers_to_select == 6


def test_adapter_unknown_lottery_raises_not_found(session):
    """Unknown lottery id raises NotFoundError like other adapters."""
    adapter = _DrawReaderAdapter(session)
    with pytest.raises(NotFoundError):
        adapter.lottery_rules(9999)
