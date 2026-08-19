"""Repository integrity tests (PR-2, P2-04).

Covers FK RESTRICT enforcement, UNIQUE rejections, IntegrityError -> typed
domain errors, natural-key idempotency, N+1 avoidance and the SQLite FK PRAGMA
wiring (validations V1-V6). All tests run against a throwaway SQLite file
migrated by alembic (default head = 0002; override with ``LIP_TEST_MIGRATION_TARGET``
to pin 0001); the real database/lip.db is never touched and alembic never runs
against it.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from alembic import command
from backend.app.core.db import _sqlite_fk_supported, build_engine
from backend.app.models import Draw, Lottery
from backend.app.repositories.dataset_draw_repository import DatasetDrawRepository
from backend.app.repositories.dataset_repository import DatasetRepository
from backend.app.repositories.draw_number_repository import DrawNumberRepository
from backend.app.repositories.draw_repository import DrawRepository
from backend.app.repositories.errors import DuplicateError, ReferentialError
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.repositories.super_number_repository import SuperNumberRepository

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# Defaults to "head" (0002); override to 0001_initial_core_domain to prove the
# performance-index revision is functionally optional (PR-5, P5-01).
MIGRATION_TARGET = os.environ.get("LIP_TEST_MIGRATION_TARGET", "head")


@pytest.fixture
def repo_db(tmp_path: Path) -> Path:
    """A tmp SQLite file with the schema applied (alembic owns the schema)."""
    db = tmp_path / "repo_test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, MIGRATION_TARGET)
    return db


@pytest.fixture
def engine(repo_db: Path):
    """App-style engine on the migrated tmp DB (SQLite FK PRAGMA wired)."""
    eng = build_engine(f"sqlite:///{repo_db}")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """A DI-style session (no autocommit) bound to the migrated tmp DB."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = factory()
    yield s
    s.close()


def _select_counter(engine):
    """Return a mutable counter of SELECT statements executed on ``engine``."""
    counts = {"n": 0}

    @event.listens_for(engine, "after_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counts["n"] += 1

    return counts


def _make_lottery(session, code: str = "LOTO") -> Lottery:
    """Create and commit a minimal lottery via the repository."""
    return LotteryRepository(session).create(
        {
            "code": code,
            "name": f"Lottery {code}",
            "country": "ES",
            "min_number": 1,
            "max_number": 49,
            "numbers_to_select": 6,
        }
    )


def _make_draw(
    session,
    lottery_id: int,
    draw_number: int = 1,
    *,
    numbers: list[int] | None = None,
    super_value: int | None = None,
) -> Draw:
    """Create a draw (with optional children) via the repositories and commit."""
    draw = DrawRepository(session).upsert_draw(
        lottery_id=lottery_id, draw_number=draw_number, draw_date=date(2026, 1, 1)
    )
    if numbers:
        DrawNumberRepository(session).add_many(draw.id, numbers)
    if super_value is not None:
        SuperNumberRepository(session).add(draw.id, super_value)
    session.commit()
    return draw


# ---------------------------------------------------------------------------
# V1 - SQLite FK PRAGMA wiring, dialect-guarded
# ---------------------------------------------------------------------------


def test_pragma_foreign_keys_active_on_sqlite_connection(engine) -> None:
    """V1: a connection from build_engine has ``PRAGMA foreign_keys`` == 1."""
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_sqlite_fk_guard_skips_non_sqlite_dialects() -> None:
    """V1: the guard is dialect-checked; PostgreSQL and others are a no-op."""
    assert _sqlite_fk_supported("sqlite") is True
    assert _sqlite_fk_supported("postgresql") is False
    assert _sqlite_fk_supported("mysql") is False


# ---------------------------------------------------------------------------
# V2 - FK RESTRICT actually enforced on SQLite (PRAGMA on)
# ---------------------------------------------------------------------------


def test_delete_lottery_with_draws_raises_referential(session) -> None:
    """V2: deleting a lottery with draws raises ReferentialError; row survives."""
    lottery = _make_lottery(session)
    _make_draw(session, lottery.id)

    with pytest.raises(ReferentialError):
        LotteryRepository(session).delete(lottery.id)

    session.rollback()
    assert session.get(Lottery, lottery.id) is not None


def test_delete_draw_referenced_by_dataset_raises_referential(session) -> None:
    """V2: deleting a draw referenced by dataset_draws raises ReferentialError."""
    lottery = _make_lottery(session)
    draw = _make_draw(session, lottery.id)
    dataset = DatasetRepository(session).create(
        {"version": "v1", "lottery_id": lottery.id, "generator_version": "g1"}
    )
    DatasetDrawRepository(session).add_many(dataset_id=dataset.id, draw_ids=[draw.id])
    session.commit()

    with pytest.raises(ReferentialError):
        DrawRepository(session).delete(draw.id)

    session.rollback()
    assert session.get(Draw, draw.id) is not None


# ---------------------------------------------------------------------------
# V3 - IntegrityError -> typed domain errors (UNIQUE -> Duplicate, FK -> Referential)
# ---------------------------------------------------------------------------


def test_duplicate_draw_raises_duplicate_error(session) -> None:
    """V3: a second draw with the same natural key raises DuplicateError."""
    lottery = _make_lottery(session)
    _make_draw(session, lottery.id, draw_number=100)

    with pytest.raises(DuplicateError):
        DrawRepository(session).create(
            {"lottery_id": lottery.id, "draw_number": 100, "draw_date": date(2026, 1, 2)}
        )
    session.rollback()


def test_duplicate_lottery_code_raises_duplicate_error(session) -> None:
    """V3: a second lottery with the same code raises DuplicateError (CD-01)."""
    _make_lottery(session, code="LOTO")
    with pytest.raises(DuplicateError):
        _make_lottery(session, code="LOTO")
    session.rollback()


def test_repeated_number_inside_draw_rejected(session) -> None:
    """V3/P2-04: repeated number in one draw raises DuplicateError (UNIQUE(draw_id, number))."""
    lottery = _make_lottery(session)
    draw = _make_draw(session, lottery.id, draw_number=1)
    with pytest.raises(DuplicateError):
        DrawNumberRepository(session).add_many(draw.id, [7, 7])
    session.rollback()


def test_second_super_number_rejected(session) -> None:
    """V3/P2-04: a second super number for the same draw raises DuplicateError (0..1)."""
    lottery = _make_lottery(session)
    draw = _make_draw(session, lottery.id, draw_number=1, super_value=3)
    with pytest.raises(DuplicateError):
        SuperNumberRepository(session).add(draw.id, 9)
    session.rollback()


def test_update_to_duplicate_code_raises_duplicate_error(session) -> None:
    """V3: PUT-style update onto an existing code raises DuplicateError."""
    first = _make_lottery(session, code="A")
    _make_lottery(session, code="B")
    with pytest.raises(DuplicateError):
        LotteryRepository(session).update(first.id, {"code": "B"})
    session.rollback()


# ---------------------------------------------------------------------------
# V4 - natural-key idempotency
# ---------------------------------------------------------------------------


def test_upsert_draw_is_idempotent(session) -> None:
    """V4: upsert_draw with the same natural key creates once and returns existing."""
    lottery = _make_lottery(session)
    repo = DrawRepository(session)

    first = repo.upsert_draw(lottery_id=lottery.id, draw_number=7, draw_date=date(2026, 1, 1))
    session.commit()
    second = repo.upsert_draw(lottery_id=lottery.id, draw_number=7, draw_date=date(2026, 1, 1))
    session.commit()

    assert first.id == second.id
    assert session.query(Draw).filter_by(lottery_id=lottery.id, draw_number=7).count() == 1


def test_get_by_natural_key_finds_draw(session) -> None:
    """V4: get_by_natural_key(lottery_id, draw_number) resolves the row."""
    lottery = _make_lottery(session)
    _make_draw(session, lottery.id, draw_number=42)
    found = DrawRepository(session).get_by_natural_key(lottery.id, 42)
    assert found is not None
    assert found.draw_number == 42
    assert DrawRepository(session).get_by_natural_key(lottery.id, 43) is None


def test_lottery_get_by_code_natural_key(session) -> None:
    """V4: the lottery natural key (``code``) resolves via get_by_code."""
    created = _make_lottery(session, code="EUROM")
    found = LotteryRepository(session).get_by_code("EUROM")
    assert found is not None
    assert found.id == created.id
    assert LotteryRepository(session).get_by_code("NOPE") is None


def test_dataset_get_by_version_natural_key(session) -> None:
    """V4: the dataset natural key (``version``) resolves via get_by_version."""
    lottery = _make_lottery(session)
    created = DatasetRepository(session).create(
        {"version": "v9", "lottery_id": lottery.id, "generator_version": "g1"}
    )
    session.commit()
    found = DatasetRepository(session).get_by_version("v9")
    assert found is not None
    assert found.id == created.id


# ---------------------------------------------------------------------------
# V5 - N+1 avoidance in defined cases (SELECT counting via engine listener)
# ---------------------------------------------------------------------------


def test_get_with_numbers_no_nplus1(engine, session) -> None:
    """V5: get_with_numbers keeps a small, child-count-independent SELECT count."""
    lottery = _make_lottery(session)
    small = _make_draw(
        session, lottery.id, draw_number=1, numbers=list(range(1, 31)), super_value=5
    )

    counter = _select_counter(engine)
    loaded = DrawRepository(session).get_with_numbers(small.id)
    small_count = counter["n"]
    assert len(loaded.numbers) == 30
    assert loaded.super_number is not None
    assert small_count == 3  # 1 draw + 1 numbers batch + 1 super batch

    big = _make_draw(session, lottery.id, draw_number=2, numbers=list(range(1, 81)), super_value=9)
    counter["n"] = 0
    loaded_big = DrawRepository(session).get_with_numbers(big.id)
    assert len(loaded_big.numbers) == 80
    assert counter["n"] == small_count  # independence from child count => no N+1


def test_list_draws_no_n_plus1(engine, session) -> None:
    """V5: a paginated draw list loads the page with a flat, page-size-independent count."""
    lottery = _make_lottery(session)
    for i in range(1, 21):
        numbers = [1, 2, 3, 4, 5]
        _make_draw(session, lottery.id, draw_number=i, numbers=numbers, super_value=i % 10)

    counter = _select_counter(engine)
    DrawRepository(session).list_draws(page=1, page_size=4, lottery_code="LOTO")
    small_page = counter["n"]
    assert small_page == 3  # 1 page query + numbers batch + super batch

    counter["n"] = 0
    DrawRepository(session).list_draws(page=1, page_size=20, lottery_code="LOTO")
    assert counter["n"] == small_page  # independence from page size => no N+1


def test_dataset_batch_load_no_n_plus1(engine, session) -> None:
    """V5: draws_for_dataset uses exactly two SELECTs regardless of composition size."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    d2 = _make_draw(session, lottery.id, draw_number=2)
    d3 = _make_draw(session, lottery.id, draw_number=3)
    dataset = DatasetRepository(session).create(
        {"version": "v1", "lottery_id": lottery.id, "generator_version": "g1"}
    )
    DatasetDrawRepository(session).add_many(dataset_id=dataset.id, draw_ids=[d1.id, d2.id, d3.id])
    session.commit()

    counter = _select_counter(engine)
    draws = DatasetDrawRepository(session).draws_for_dataset(dataset.id)
    assert counter["n"] == 2  # 1 join scan + 1 IN query
    assert [d.id for d in draws] == [d1.id, d2.id, d3.id]


# ---------------------------------------------------------------------------
# Functional CRUD + pagination + filters
# ---------------------------------------------------------------------------


def test_list_draws_filters_by_lottery_code(session) -> None:
    """CD-07: ``?lottery=LOTO`` returns only that lottery's draws."""
    lota = _make_lottery(session, code="A")
    lotb = _make_lottery(session, code="B")
    _make_draw(session, lota.id, draw_number=1)
    _make_draw(session, lota.id, draw_number=2)
    _make_draw(session, lotb.id, draw_number=1)

    draws = DrawRepository(session).list_draws(lottery_code="A")
    assert len(draws) == 2
    assert all(d.lottery.code == "A" for d in draws)


def test_list_draws_date_range_and_order(session) -> None:
    """CD-07: date_from/date_to filter and desc ordering on draw_date."""
    lottery = _make_lottery(session)
    for num, day in [(1, 1), (2, 2), (3, 3)]:
        repo = DrawRepository(session)
        repo.upsert_draw(lottery_id=lottery.id, draw_number=num, draw_date=date(2026, 1, day))
        session.commit()

    subset = DrawRepository(session).list_draws(date_from=date(2026, 1, 2))
    assert [d.draw_number for d in subset] == [3, 2]  # desc order on draw_date

    ordered_asc = DrawRepository(session).list_draws(order="asc")
    assert [d.draw_number for d in ordered_asc] == [1, 2, 3]


def test_generic_crud_list_pagination_and_update(session) -> None:
    """BaseRepository: create/list/paginate/update/get work generically."""
    repo = LotteryRepository(session)
    for code in ("A", "B", "C"):
        repo.create(
            {
                "code": code,
                "name": code,
                "country": "ES",
                "min_number": 1,
                "max_number": 49,
                "numbers_to_select": 6,
            }
        )
    session.commit()

    assert len(repo.list(page=1, page_size=2)) == 2
    assert len(repo.list(page=2, page_size=2)) == 1

    updated = repo.update(repo.get_by_code("A").id, {"name": "renamed"})
    assert updated is not None and updated.name == "renamed"

    assert repo.update(9999, {"name": "ghost"}) is None
    assert repo.delete(9999) is False


# ---------------------------------------------------------------------------
# V6 - cross-dialect portability smoke (SQLite host; PG is CI-gated via G6)
# ---------------------------------------------------------------------------


def test_dialect_smoke_runs_entire_repo_surface_on_sqlite(session) -> None:
    """V6: the full repository surface runs on SQLite without any dialect SQL.

    PostgreSQL parity is enforced by the same SQLAlchemy-portable code (reviewed
    in G6) plus a CI-gated dialect smoke test added in PR-5; when ``LIP_TEST_PG_URL``
    is not set this SQLite smoke is the executable portal gate and must pass.
    """
    lottery = _make_lottery(session, code="SMOKE")
    draw = DrawRepository(session).upsert_draw(
        lottery_id=lottery.id, draw_number=1, draw_date=date(2026, 1, 1), jackpot=1234567.89
    )
    DrawNumberRepository(session).add_many(draw.id, [1, 2, 3, 4, 5])
    SuperNumberRepository(session).add(draw.id, 7)
    dataset = DatasetRepository(session).create(
        {"version": "smoke-v1", "lottery_id": lottery.id, "generator_version": "g1"}
    )
    DatasetDrawRepository(session).add_many(dataset_id=dataset.id, draw_ids=[draw.id])
    session.commit()

    assert DrawRepository(session).get_with_numbers(draw.id).numbers
    assert DatasetDrawRepository(session).draws_for_dataset(dataset.id) == [draw]
