"""Lottery domain service: CRUD use cases over one DI session (CD-01; PR-4).

The API layer must never touch repositories directly (mandate: every operation
goes through services), so lottery CRUD — the only Fase 1 resource with full
GET/POST/PUT/DELETE — gets its own service. It owns the session transaction
(``begin -> flush -> commit`` with rollback on any failure) and surfaces the
typed domain errors the API maps to HTTP: ``NotFoundError`` for a missing row,
``DuplicateError`` (DUPLICATE_RESOURCE) for a UNIQUE ``code`` conflict and
``ReferentialError`` (REFERENTIAL_CONSTRAINT) when a lottery still referenced by
draws cannot be deleted (CD-05 FK RESTRICT) — both pass through untouched from
the repository, carrying their envelope codes (design, scope items 3-4).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models import Lottery
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import NotFoundError


class LotteryService:
    """Lottery use cases over one DI session transaction (CD-01 CRUD)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lotteries = LotteryRepository(session)

    def create(self, data: dict) -> Lottery:
        """Create a lottery; a duplicate ``code`` surfaces ``DuplicateError`` (409)."""
        try:
            lottery = self._lotteries.create(data)
            self._session.commit()
            return lottery
        except Exception:
            self._session.rollback()
            raise

    def get(self, lottery_id: int) -> Lottery:
        """Functional lookup by id; a missing row maps to ``NotFoundError`` (404)."""
        lottery = self._lotteries.get(lottery_id)
        if lottery is None:
            raise NotFoundError(f"lottery {lottery_id} does not exist")
        return lottery

    def list(self, *, page: int = 1, page_size: int = 50) -> list[Lottery]:
        """Page of lotteries ordered by id."""
        return self._lotteries.list(page=page, page_size=page_size)

    def update(self, lottery_id: int, data: dict) -> Lottery:
        """Apply the mutable-field mapping; a duplicate ``code`` surfaces 409."""
        self.get(lottery_id)  # raises NotFoundError when absent
        try:
            updated = self._lotteries.update(lottery_id, data)
            self._session.commit()
            return updated
        except Exception:
            self._session.rollback()
            raise

    def delete(self, lottery_id: int) -> None:
        """Delete a lottery; FK RESTRICT with existing draws surfaces 409 (CD-05).

        The repository's delete maps any ``IntegrityError`` to
        ``ReferentialError`` (REFERENTIAL_CONSTRAINT) because a bare row removal
        can only be blocked by a referencing row — the API reports 409 and the
        lottery remains.
        """
        self.get(lottery_id)  # raises NotFoundError when absent
        try:
            self._lotteries.delete(lottery_id)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
