"""Data-access boundary: declarative Base, engine and session factory built from settings."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.db import build_engine


class Base(DeclarativeBase):
    """Declarative base for ORM entities; Fase 1 schema subclasses this."""


engine: Engine = build_engine()
"""Application-wide SQLAlchemy engine, built from the configured database URL."""

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
"""Session factory bound to the application engine (one session per request)."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for dependency injection.

    Rolls back on error and always closes the session afterwards.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
