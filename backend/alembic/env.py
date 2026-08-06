"""Alembic environment: sole schema owner (REQ-09), dialect-driven engine, batch mode.

``target_metadata`` is ``Base.metadata`` from the models package so the migration
set mirrors the declared ORM schema exactly. ``render_as_batch=True`` enables
SQLite ``batch_mode`` (portable DDL). The engine URL resolves from the alembic
``sqlalchemy.url`` override if set (used by tests) else from app settings.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

# Make the src-layout package importable regardless of the invocation directory.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _BACKEND_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from alembic import context  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402

from backend.app.config.settings import get_settings  # noqa: E402

# Importing the models package registers every table on Base.metadata.
from backend.app.models import Base  # noqa: F401, E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the engine URL: explicit alembic override wins, else app settings."""
    explicit = config.get_main_option("sqlalchemy.url")
    return explicit if explicit else get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode: emit SQL without a DB connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the configured engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
