"""Isolation guard for the shared-connection savepoint fixtures (T-S7-03).

Test A seeds + commits; test B must see empty tables.  This is the regression
net for the session-scoped connection / ``create_savepoint`` infrastructure —
if the outer transaction rollback ever breaks, these two tests fail together.
"""

from __future__ import annotations

from sqlalchemy import select

from backend.app.models import Lottery
from backend.app.services.lottery_service import LotteryService

_LOTTERY = {
    "code": "ISO",
    "name": "Isolation",
    "country": "AR",
    "min_number": 1,
    "max_number": 9,
    "numbers_to_select": 4,
    "super_number_min": 1,
    "super_number_max": 3,
}


def test_a_seeds_and_commits(db) -> None:
    """First test in a suite run: seed a lottery and commit it."""
    LotteryService(db).create({**_LOTTERY})
    db.commit()
    rows = db.execute(select(Lottery)).scalars().all()
    assert len(rows) == 1


def test_b_asserts_tables_empty(db) -> None:
    """Second test must start from an empty lottery table (no leakage)."""
    rows = db.execute(select(Lottery)).scalars().all()
    assert rows == []
