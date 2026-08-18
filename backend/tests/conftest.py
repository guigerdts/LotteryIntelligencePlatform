"""Shared fixtures for the F16 test infrastructure (CD-07 + T-S7-01/02/04).

Builds ONE throwaway SQLite file migrated by alembic once per pytest session
(session-scoped; default target = head, set ``LIP_TEST_MIGRATION_TARGET`` to
pin 0001) and holds ONE shared connection with an outer transaction.  Every
per-test session joins that outer transaction via
``join_transaction_mode="create_savepoint"``; an autouse fixture rolls the
outer transaction back after every test, so committed rows never leak between
tests while a single schema build + a single connection keep per-test setup at
milliseconds (PFM-02; baseline was ~3 s/test).

KNOWN TEST-ENV CONSTRAINT (PFM-06/T-S7-04): the full backend suite peaks at
~1 GB RAM — run app-backed dirs (statistics/api/gen/bt) per-directory on a
2.4 GB box; an OOM kill is a memory limit, not a fixture defect.

The real ``database/lip.db`` is never migrated nor written by the schema (the
app still boots its empty file via ``init_db`` as the Fase 0 bootstrap,
matching the existing smoke tests).  Services used to seed state (lotteries,
draws) run over the same shared connection, so API reads see the same
committed rows.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.response_cache import clear_all_caches
from backend.app.main import create_app
from backend.app.repositories.base import get_db

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# Default migration target is "head". Running the suite with
# LIP_TEST_MIGRATION_TARGET=0001_initial_core_domain proves 0002 is functionally
# optional (the app works with only 0001 applied; 0002 only adds indexes).
MIGRATION_TARGET = os.environ.get("LIP_TEST_MIGRATION_TARGET", "head")


def _wire_sqlite_fk(engine) -> None:
    """Enable SQLite FK enforcement for the test engine (mirrors core/db.py)."""

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, _record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(autouse=True)
def _reset_response_caches() -> None:
    """Clear the in-process response caches before every test (PFM-05)."""
    clear_all_caches()


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One session tmp SQLite file with the schema applied (T-S7-01)."""
    db = tmp_path_factory.mktemp("api_tests") / "session.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, MIGRATION_TARGET)
    return db


@pytest.fixture(scope="session")
def api_engine(migrated_db: Path):
    """App-style engine on the session tmp DB (single shared connection, T-S7-01).

    Two flags make SAVEPOINT semantics correct on SQLite: the dialect-level
    ``isolation_level="AUTOCOMMIT"`` stops the pysqlite driver's legacy
    implicit-BEGIN handling from fighting SQLAlchemy's transaction state, and
    ``connect_args={"autocommit": False}`` enables the modern sqlite3
    transaction mode (Python 3.12+). Together they ensure
    ``connection.rollback()`` genuinely discards released savepoints instead of
    leaving data durable (verified empirically against a raw-sqlite control).
    """
    engine = create_engine(
        f"sqlite:///{migrated_db}",
        isolation_level="AUTOCOMMIT",
        connect_args={"autocommit": False, "check_same_thread": False},
    )
    _wire_sqlite_fk(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def connection(api_engine):
    """One session-wide connection holding the outer transaction (T-S7-01)."""
    conn = api_engine.connect()
    conn.begin()
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(scope="session")
def session_factory(connection) -> sessionmaker[Session]:
    """Savepoint-joining session factory bound to the shared connection (T-S7-02)."""
    return sessionmaker(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture(autouse=True)
def _reset_outer_transaction(connection) -> Iterator[None]:
    """Discard every test's writes — the per-test isolation net (T-S7-02).

    Runs after every test's own fixtures close their sessions: roll back the
    outer transaction (discarding every released savepoint) and immediately
    re-begin a fresh one, so the next test's sessions join a savepoint again
    instead of starting a durable transaction.
    """
    yield
    connection.rollback()
    connection.begin()


@pytest.fixture
def db(session_factory) -> Iterator[Session]:
    """A direct savepoint session over the shared connection, for seeding."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory) -> Iterator[TestClient]:
    """A TestClient whose ``get_db`` dependency targets the shared connection."""

    def _override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
