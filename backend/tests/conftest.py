"""Shared fixtures for the PR-4 API tests (CD-07).

Builds a throwaway SQLite file migrated by alembic (default head = 0002; set
``LIP_TEST_MIGRATION_TARGET`` to pin 0001) and overrides the app's
``get_db`` dependency so every request hits that tmp DB — the real
``database/lip.db`` is never migrated nor written by the schema (the app still
boots its empty file via ``init_db`` as the Fase 0 bootstrap, matching the
existing smoke tests). Services used to seed F1 state (lotteries, draws) run over
the same session factory, so API reads see the same committed rows.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.main import create_app
from backend.app.repositories.base import get_db

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# Default migration target is "head" (0002). Running the suite with
# LIP_TEST_MIGRATION_TARGET=0001_initial_core_domain proves 0002 is functionally
# optional (the app works with only 0001 applied; 0002 only adds indexes).
MIGRATION_TARGET = os.environ.get("LIP_TEST_MIGRATION_TARGET", "head")


@pytest.fixture
def migrated_db(tmp_path: Path) -> Path:
    """A tmp SQLite file with the schema applied (alembic owns the schema)."""
    db = tmp_path / "api_test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, MIGRATION_TARGET)
    return db


@pytest.fixture
def api_engine(migrated_db: Path):
    """App-style engine on the migrated tmp DB (SQLite FK PRAGMA wired)."""
    eng = build_engine(f"sqlite:///{migrated_db}")
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(api_engine) -> sessionmaker[Session]:
    """Session factory bound to the tmp migrated DB (same one the app uses)."""
    return sessionmaker(bind=api_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(session_factory) -> Iterator[Session]:
    """A direct DI-style session over the tmp DB, for seeding test state."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory) -> Iterator[TestClient]:
    """A TestClient whose ``get_db`` dependency targets the tmp migrated DB."""

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
