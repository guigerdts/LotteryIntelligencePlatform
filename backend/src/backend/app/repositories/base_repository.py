"""Generic repository base: CRUD over the DI ``Session``, no business logic.

Transaction pattern (scope item 4): repository operations run inside the
session transaction opened by the caller (the domain service owns the commit in
PR-3; ``get_db`` rolls back on error). Repositories only ``flush()`` where a
constraint must surface immediately — so ``IntegrityError`` is raised inside the
repository call, where it is translated to a typed domain error
(:mod:`backend.app.repositories.errors`) — and never commit.

``create``/``update`` map UNIQUE/FK failures to ``DuplicateError`` /
``ReferentialError``; ``delete`` maps any IntegrityError to ``ReferentialError``
because a bare row removal can only be blocked by a referencing row.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.repositories.base import Base
from backend.app.repositories.errors import ReferentialError, translate_integrity_error


class BaseRepository[ModelT: Base]:
    """Minimal generic CRUD over one DI session (no commits, no business rules).

    Subclasses declare ``model`` and add entity-specific loading/idempotency
    primitives; this class de-duplicates the four basic operations.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, id: int) -> ModelT | None:
        """Return the row by primary key, or ``None`` when absent."""
        return self._session.get(self.model, id)

    def list(self, *, page: int = 1, page_size: int = 50) -> list[ModelT]:
        """Return a page of rows ordered by primary key (ORM instances only)."""
        stmt = (
            select(self.model)
            .order_by(self.model.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self._session.scalars(stmt).all())

    def create(self, data: dict) -> ModelT:
        """Insert a row from a plain mapping; flush surfaces UNIQUE/FK failures."""
        instance = self.model(**data)
        self._session.add(instance)
        self._flush(operation="create")
        return instance

    def update(self, id: int, data: dict) -> ModelT | None:
        """Apply the mapping to an existing row; ``None`` when the row is absent.

        A UNIQUE conflict (e.g. duplicate ``lottery.code``) raises
        ``DuplicateError`` from the flush; no commit is issued here.
        """
        instance = self.get(id)
        if instance is None:
            return None
        for key, value in data.items():
            setattr(instance, key, value)
        self._flush(operation="update")
        return instance

    def delete(self, id: int) -> bool:
        """Hard-delete a row; ``False`` when absent.

        Any IntegrityError raised by the flush means another row still
        references this one (FK RESTRICT, or the SQLite NOT-NULL cascade
        artifact) and is translated to ``ReferentialError``.
        """
        instance = self.get(id)
        if instance is None:
            return False
        self._session.delete(instance)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise ReferentialError(
                "operation blocked: the row is referenced by another record",
                constraint=exc.orig,
            ) from exc
        return True

    def _flush(self, *, operation: str) -> None:
        """Flush the session and translate any IntegrityError to a domain error."""
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise translate_integrity_error(exc, operation=operation) from exc
