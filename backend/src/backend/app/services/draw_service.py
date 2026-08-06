"""Draw domain service: atomic bundle creation, soft-delete/restore, CD-05 queries.

Hosts the use cases the repositories must not own (design, scope item 3):
cross-entity invariants (CD-06), the one-transaction boundary for a draw plus
its children, soft-delete policy, and error-to-envelope-code mapping. The
repositories stay persistence-only; this service owns the session transaction
(``begin -> flush -> commit``, rollback on any failure) so no partially
persisted state — zero orphan rows and zero incomplete bundles ever survive
(mandate B). Idempotency for reproducible batches (mandate A / Req 4): a
natural key that already exists returns the existing draw without re-inserting.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.models.draw import Draw
from backend.app.models.lottery import Lottery
from backend.app.repositories.draw_number_repository import DrawNumberRepository
from backend.app.repositories.draw_repository import DrawRepository
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.repositories.super_number_repository import SuperNumberRepository
from backend.app.services.errors import NotFoundError, SoftDeletedError, ValidationError
from backend.app.services.helpers import get_lottery_or_raise


class DrawService:
    """Draw use cases over one DI session transaction (atomic, idempotent, CD-05)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lotteries = LotteryRepository(session)
        self._draws = DrawRepository(session)
        self._numbers = DrawNumberRepository(session)
        self._supers = SuperNumberRepository(session)

    def create_draw_bundle(
        self,
        *,
        lottery_id: int,
        draw_number: int,
        draw_date: date,
        numbers: list[int],
        super_number: int | None = None,
        jackpot: Decimal | None = None,
        winners: int | None = None,
    ) -> Draw:
        """Create a draw with its numbers and optional super number in one transaction.

        Idempotency (mandate A / Req 4): the natural key
        ``UNIQUE(lottery_id, draw_number)`` is checked first — an existing draw
        is returned untouched (``get_with_numbers``), so a replayed F2 batch
        resumes instead of failing (``exist-return`` conflict strategy; a
        concurrent race may still surface ``DuplicateError`` from the DB, which
        the importer treats as "already imported").

        Service-owned invariants (CD-06) are validated before any insert: the
        drawn count must equal the lottery's ``numbers_to_select``, every number
        must lie within the lottery's range, no number may repeat, and a provided
        super number must fit the lottery's defined range. Duplicate / referential
        failures still surface as ``DuplicateError`` / ``ReferentialError`` from
        the DB constraint backstop; the operation rolls back atomically (mandate
        B), leaving zero draw rows, zero number rows and zero super rows on any
        failure after the draw insert.
        """
        lottery = get_lottery_or_raise(self._lotteries, lottery_id)

        existing = self._draws.get_by_natural_key(lottery_id, draw_number)
        if existing is not None:
            return self._draws.get_with_numbers(existing.id)

        self._validate_numbers(lottery, numbers)
        self._validate_super_number(lottery, super_number)

        try:
            draw = self._draws.create(
                {
                    "lottery_id": lottery_id,
                    "draw_number": draw_number,
                    "draw_date": draw_date,
                    "jackpot": jackpot,
                    "winners": winners,
                    "is_deleted": False,
                }
            )
            self._numbers.add_many(draw.id, numbers)
            if super_number is not None:
                self._supers.add(draw.id, super_number)
            self._session.commit()
            return self._draws.get_with_numbers(draw.id)
        except Exception:
            self._session.rollback()
            raise

    def soft_delete(self, draw_id: int) -> Draw:
        """Mark a draw soft-deleted; children (numbers, super_number) are untouched (CD-05).

        Referential integrity is preserved: the FK RESTRICT children keep their
        rows, so a later restore brings the draw back with all children intact.
        Idempotent — a draw already soft-deleted is left soft-deleted.
        """
        draw = self._require_draw(draw_id)
        try:
            self._draws.update(draw_id, {"is_deleted": True})
            self._session.commit()
            return draw
        except Exception:
            self._session.rollback()
            raise

    def restore(self, draw_id: int) -> Draw:
        """Restore a soft-deleted draw; its numbers and super number come back intact (CD-05)."""
        draw = self._require_draw(draw_id)
        try:
            self._draws.update(draw_id, {"is_deleted": False})
            self._session.commit()
            return draw
        except Exception:
            self._session.rollback()
            raise

    def get_draw(self, draw_id: int) -> Draw:
        """Functional draw lookup that ALWAYS excludes soft-deleted draws (CD-05).

        Absent → ``NotFoundError`` (RESOURCE_NOT_FOUND); an explicit access to a
        soft-deleted draw → ``SoftDeletedError`` (RESOURCE_SOFT_DELETED, 404).
        Administrative access to soft-deleted rows stays available via the
        repository primitives (raw ``get``), keeping the audit row readable.
        """
        draw = self._draws.get_with_numbers(draw_id)
        if draw is None:
            raise NotFoundError(f"draw {draw_id} does not exist")
        if draw.is_deleted:
            raise SoftDeletedError(f"draw {draw_id} is soft-deleted")
        return draw

    def list_draws(
        self,
        *,
        lottery_code: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> list[Draw]:
        """Functional page of draws, ALWAYS excluding soft-deleted rows (CD-05).

        The service owns the exclusion policy (always ``is_deleted=False``); the
        repository applies it in SQL so pagination stays correct.
        """
        return self._draws.list_draws(
            lottery_code=lottery_code,
            date_from=date_from,
            date_to=date_to,
            order=order,
            page=page,
            page_size=page_size,
            is_deleted=False,
        )

    # --- private helpers ---------------------------------------------------

    def _require_draw(self, draw_id: int) -> Draw:
        """Administrative draw lookup by id, any soft-delete state (never filtered)."""
        draw = self._draws.get(draw_id)
        if draw is None:
            raise NotFoundError(f"draw {draw_id} does not exist")
        return draw

    def _validate_numbers(self, lottery: Lottery, numbers: list[int]) -> None:
        """Service-owned (CD-06) invariant checks against the lottery's rules."""
        if len(numbers) != lottery.numbers_to_select:
            raise ValidationError(
                f"draw must select {lottery.numbers_to_select} numbers, got {len(numbers)}"
            )
        if any(number < lottery.min_number or number > lottery.max_number for number in numbers):
            raise ValidationError(
                f"numbers must be within [{lottery.min_number}, {lottery.max_number}]"
            )
        if len(set(numbers)) != len(numbers):
            raise ValidationError("numbers must not repeat within a draw")

    def _validate_super_number(self, lottery: Lottery, super_number: int | None) -> None:
        """Service-owned check for the optional super number against the lottery's range."""
        if super_number is None:
            return
        if lottery.super_number_min is None or lottery.super_number_max is None:
            raise ValidationError("lottery does not define a super number range")
        if super_number < lottery.super_number_min or super_number > lottery.super_number_max:
            raise ValidationError(
                "super number must be within "
                f"[{lottery.super_number_min}, {lottery.super_number_max}]"
            )
