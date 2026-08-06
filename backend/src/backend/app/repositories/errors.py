"""Typed domain errors surfaced by the repository layer from DB constraint failures.

Repositories catch ``sqlalchemy.exc.IntegrityError`` and re-raise a typed domain
error carrying an envelope ``code`` attribute (PR-4 maps these to HTTP 409
``DUPLICATE_RESOURCE`` / ``REFERENTIAL_CONSTRAINT``). Detection is portable and
dialect-isolated inside the repository boundary:

* INSERT/UPDATE failures are classified by scanning the underlying DBAPI message
  for dialect-neutral markers. SQLite emits ``UNIQUE constraint failed`` /
  ``FOREIGN KEY constraint failed``; PostgreSQL emits ``duplicate key value
  violates unique constraint`` / ``violates foreign key constraint``.
* DELETE failures are always mapped to ``ReferentialError``: removing a row can
  never violate UNIQUE/CHECK/NOT NULL, so any IntegrityError raised while
  deleting means another row still references it. SQLite surfaces FK RESTRICT as
  a NOT-NULL cascade artifact (the ORM first tries to NULL the child FK, which
  the NOT NULL column forbids), which the generic markers would misread — hence
  the operation-aware mapping.

No dialect-specific code path exists outside this module; the heuristics are
message-based so SQLite and PostgreSQL share one implementation.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


class RepositoryError(Exception):
    """Base class for repository-layer domain errors (typed DB failures)."""

    code: str = "RESOURCE_ERROR"

    def __init__(self, message: str, *, constraint: str | None = None) -> None:
        self.constraint = constraint
        super().__init__(message)


class DuplicateError(RepositoryError):
    """A UNIQUE constraint was violated. Envelope code ``DUPLICATE_RESOURCE``."""

    code = "DUPLICATE_RESOURCE"


class ReferentialError(RepositoryError):
    """An FK (RESTRICT) constraint blocked the operation. Code ``REFERENTIAL_CONSTRAINT``."""

    code = "REFERENTIAL_CONSTRAINT"


# Dialect-neutral markers inside DBAPI messages (SQLite / PostgreSQL flavours).
_UNIQUE_MARKERS = ("unique constraint failed", "duplicate key", "unique constraint")
_FK_MARKERS = (
    "foreign key constraint failed",
    "violates foreign key constraint",
    "foreign key constraint",
)


def translate_integrity_error(exc: IntegrityError, *, operation: str) -> RepositoryError:
    """Translate an ``IntegrityError`` into a typed domain error.

    ``operation`` is one of ``create`` / ``update`` / ``delete``. Deletes are
    referential by construction (see module docstring); create/update are
    classified by dialect-neutral message markers.
    """
    raw = exc.orig if exc.orig is not None else exc
    message = str(raw)
    lowered = message.lower()

    if operation == "delete":
        return ReferentialError(
            "operation blocked: the row is referenced by another record",
            constraint=_constraint_name(message),
        )

    if any(marker in lowered for marker in _FK_MARKERS):
        return ReferentialError(message, constraint=_constraint_name(message))

    if any(marker in lowered for marker in _UNIQUE_MARKERS):
        return DuplicateError(message, constraint=_constraint_name(message))

    # Any other constraint failure on write stays typed but generic.
    return RepositoryError(message, constraint=_constraint_name(message))


def _constraint_name(message: str) -> str | None:
    """Best-effort constraint name extraction from a DBAPI message (may be None)."""
    # SQLite: "UNIQUE constraint failed: lottery.code" -> table.column list.
    if "constraint failed:" in message:
        return message.split("constraint failed:", 1)[1].strip()
    # PostgreSQL: 'duplicate key value violates unique constraint "uq_lottery_code"'.
    if '"' in message and "constraint" in message.lower():
        quoted = message.split('"', 1)[1]
        return quoted.split('"', 1)[0]
    return None
