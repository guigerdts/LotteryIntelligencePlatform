"""Dialect compatibility smoke tests (CD-08, REQ-09, PR-5 P5-03).

Proves the schema, repositories, services and API are dialect-portable:

* SQLite host (always runs): the identical alembic migration set (head = 0002)
  plus a repo/service/API smoke against a throwaway SQLite file — the same
  code paths the PG tests exercise, so the suite stays executable everywhere.
* PostgreSQL (CI-gated): the identical migrations + repo/service/API smoke run
  against a real Postgres when ``TEST_POSTGRES_URL`` or ``DATABASE_URL_PG`` is
  set AND the ``psycopg`` driver is importable (install via
  ``uv sync --extra dialect-pg``). Without either, the test skips cleanly with
  an explicit message — no PG server is required for local runs, and no
  engine-specific code exists anywhere (portable ops only, G6).

The real ``database/lip.db`` is never migrated or written.
"""

from __future__ import annotations

import importlib.util
import os
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.main import create_app
from backend.app.repositories.base import get_db
from backend.app.services.draw_service import DrawService
from backend.app.services.lottery_service import LotteryService

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

_EXPECTED_TABLES = {
    "lottery",
    "draw",
    "draw_numbers",
    "super_number",
    "datasets",
    "dataset_draws",
}

# The four performance indexes 0002 must create on ANY dialect (G6).
_EXPECTED_PERF_INDEXES = {
    "ix_draw_lottery_date": ("draw", ("lottery_id", "draw_date")),
    "ix_draw_lottery_id": ("draw", ("lottery_id",)),
    "ix_draw_numbers_draw_id": ("draw_numbers", ("draw_id",)),
    "ix_dataset_draws_draw_id": ("dataset_draws", ("draw_id",)),
}


def _pg_url_from_env() -> str | None:
    """Return the configured PostgreSQL URL, or ``None`` when unset."""
    return os.environ.get("TEST_POSTGRES_URL") or os.environ.get("DATABASE_URL_PG")


def _psycopg_available() -> bool:
    """True when the optional ``psycopg`` driver is importable (dialect-pg extra)."""
    return importlib.util.find_spec("psycopg") is not None


def _seed_and_assert(engine) -> None:
    """Seed via the domain services and exercise the repo surface (no API)."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        lottery = LotteryService(session).create(
            {
                "code": "LOTO",
                "name": "Lottery LOTO",
                "country": "ES",
                "min_number": 1,
                "max_number": 49,
                "numbers_to_select": 6,
                "super_number_min": 1,
                "super_number_max": 10,
            }
        )
        draw = DrawService(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=[1, 2, 3, 4, 5, 6],
            super_number=7,
        )
        loaded = DrawService(session).get_draw(draw.id)
        assert len(loaded.numbers) == 6
        assert loaded.super_number is not None and loaded.super_number.value == 7

        listed = DrawService(session).list_draws(lottery_code="LOTO")
        assert [d.draw_number for d in listed] == [1]


def _api_smoke(engine) -> None:
    """Boot the app with ``get_db`` overridden to the target engine and read via HTTP."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override_get_db():
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        response = client.get("/api/v1/draws", params={"lottery": "LOTO"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["draw_number"] == 1


def _assert_perf_indexes(engine) -> None:
    """The four 0002 performance indexes exist on the target dialect."""
    insp = inspect(engine)
    for name, (table, columns) in _EXPECTED_PERF_INDEXES.items():
        by_name = {i["name"]: i for i in insp.get_indexes(table)}
        assert name in by_name, f"missing {name} on {table}"
        assert tuple(by_name[name]["column_names"]) == columns


# ---------------------------------------------------------------------------
# SQLite — ALWAYS runs (the executable portal gate; PG is CI-gated)
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine(tmp_path: Path):
    """A tmp SQLite DB migrated to head (0002) by the exact alembic migration set."""
    db = tmp_path / "dialect_sqlite.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db}")
    yield engine
    engine.dispose()


def test_sqlite_migrations_repo_service_api_smoke(sqlite_engine) -> None:
    """SQLite: identical migrations create the schema + indexes; repo/service/API run."""
    insp = inspect(sqlite_engine)
    assert {t for t in insp.get_table_names()} >= _EXPECTED_TABLES
    _assert_perf_indexes(sqlite_engine)
    _seed_and_assert(sqlite_engine)
    _api_smoke(sqlite_engine)


def test_sqlite_indexes_are_explicit_create_indexes(sqlite_engine) -> None:
    """SQLite: the four perf indexes are explicit (sql IS NOT NULL in sqlite_master)."""
    with sqlite_engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT name, sql FROM sqlite_master WHERE type='index'").all()
    master = {name: sql for name, sql in rows}
    for name in _EXPECTED_PERF_INDEXES:
        assert master.get(name) is not None, f"{name} is not an explicit CREATE INDEX"


# ---------------------------------------------------------------------------
# PostgreSQL — CI-gated: skips cleanly when the URL or the driver is unavailable
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_url() -> str:
    """The PostgreSQL URL from the environment; skips the suite when unavailable.

    Set ``TEST_POSTGRES_URL`` (or ``DATABASE_URL_PG``) to
    ``postgresql+psycopg://user:pass@host:5432/dbname`` and install the optional
    driver with ``uv sync --extra dialect-pg``. Without either, the PostgreSQL
    dialect smoke cannot run here and skips with this explicit message — the
    SQLite tests above remain the executable portability gate (G6).
    """
    url = _pg_url_from_env()
    if url is None:
        pytest.skip(
            "TEST_POSTGRES_URL/DATABASE_URL_PG not set — PostgreSQL dialect smoke "
            "is CI-gated; run the SQLite smoke (always on) for the executable "
            "portability gate."
        )
    if not _psycopg_available():
        pytest.skip(
            "psycopg driver not importable — install the optional extra with "
            "'uv sync --extra dialect-pg' to run the PostgreSQL dialect smoke."
        )
    return url


def test_postgres_migrations_repo_service_api_smoke(pg_url: str) -> None:
    """PG: the identical migration set + repo/service/API smoke (CI-gated).

    ``alembic upgrade head`` creates the six tables and the four performance
    indexes via the very same portable ops used on SQLite; then the services and
    the HTTP layer run unchanged against Postgres. Downgrade to base leaves the
    schema empty, proving the migration set round-trips on both dialects.
    """
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")

    engine = sa.create_engine(pg_url)
    try:
        insp = inspect(engine)
        assert {t for t in insp.get_table_names()} >= _EXPECTED_TABLES
        _assert_perf_indexes(engine)
        _seed_and_assert(engine)
        _api_smoke(engine)
    finally:
        engine.dispose()

    command.downgrade(cfg, "base")
    with sa.create_engine(pg_url).connect() as conn:
        remaining = {t for t in inspect(conn).get_table_names()} - {"alembic_version"}
    assert remaining == set()
