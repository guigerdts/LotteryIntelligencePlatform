"""Database bootstrap: SQLAlchemy engine construction and empty database file creation."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from backend.app.config.settings import get_settings


def _enable_sqlite_fk(dbapi_connection, connection_record) -> None:
    """Enable SQLite foreign-key enforcement for a new connection.

    SQLite does NOT enforce FK constraints unless ``PRAGMA foreign_keys=ON`` is
    issued per connection (the default is OFF). This handler is registered ONLY
    on SQLite engines via :func:`_wire_sqlite_fk`; on PostgreSQL (which enforces
    FKs natively) the handler is never attached, so it is a strict no-op there.
    The guard on the dialect ensures the SQLite-only PRAGMA never runs against a
    non-SQLite backend (scope: SQLite-only FK wiring, config-only PG swap).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _sqlite_fk_supported(dialect_name: str) -> bool:
    """Return True only for the SQLite dialect.

    Formalizes the dialect guard so the "skip non-SQLite dialects" behaviour is
    unit-testable without a live PostgreSQL driver. PostgreSQL is a no-op.
    """
    return dialect_name == "sqlite"


def _wire_sqlite_fk(engine: Engine) -> None:
    """Attach the FK PRAGMA handler to ``engine`` when its dialect is SQLite."""
    if _sqlite_fk_supported(engine.dialect.name):
        event.listen(engine, "connect", _enable_sqlite_fk)


def build_engine(database_url: str | None = None) -> Engine:
    """Build the SQLAlchemy engine from the configured database URL.

    The dialect is driven entirely by the URL (SQLite today, PostgreSQL later as
    a config-only swap); no dialect-specific behavior is hard-coded here. For
    SQLite engines only, the connection-level ``PRAGMA foreign_keys=ON`` is
    wired so FK RESTRICT constraints actually take effect (see scope item 3).
    """
    url = database_url or get_settings().database_url
    engine = create_engine(url)
    _wire_sqlite_fk(engine)
    return engine


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
