"""Database bootstrap: SQLAlchemy engine construction and empty database file creation."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.app.config.settings import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    """Build the SQLAlchemy engine from the configured database URL.

    The dialect is driven entirely by the URL (SQLite today, PostgreSQL later as
    a config-only swap); no dialect-specific behavior is hard-coded here.
    """
    url = database_url or get_settings().database_url
    return create_engine(url)


def init_db(database_url: str | None = None) -> Path:
    """Create an empty database file at the configured path; no schema is created.

    Local-file dialects (SQLite) require a filesystem step; remote dialects have
    nothing to create. Schema is owned exclusively by the Fase 1 alembic
    migrations (REQ-09): ``Base.metadata.create_all`` is never used, and the
    schema exists only after ``alembic upgrade head``.
    """
    settings = get_settings()
    url = database_url or settings.database_url
    path = Path(settings.database_path)

    if url.startswith("sqlite"):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Connecting with a SQLite URL creates the file with zero tables.
        engine = build_engine(url)
        with engine.connect():
            pass
        engine.dispose()

    return path
