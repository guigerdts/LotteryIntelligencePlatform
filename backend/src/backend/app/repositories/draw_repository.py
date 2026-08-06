"""Draw repository: natural-key lookup, eager child loading and the idempotent upsert.

Loading strategy owner (design, Req 6): every query that serializes a draw loads
``numbers`` and ``super_number`` eagerly (selectin) and joins ``lottery``, so the
API/service never lazy-loads inside loops (N+1 avoidance, scope item 8).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import contains_eager, selectinload

from backend.app.models import Draw, Lottery
from backend.app.repositories.base_repository import BaseRepository


class DrawRepository(BaseRepository[Draw]):
    """CRUD + draw-specific loading/idempotency primitives over the DI session."""

    model = Draw

    def get_by_natural_key(self, lottery_id: int, draw_number: int) -> Draw | None:
        """Existence check on the natural key ``UNIQUE(lottery_id, draw_number)``.

        The idempotent-import contract (design, Req 4): F2 batch retries rely on
        this primitive before any insert.
        """
        return self._session.scalar(
            select(Draw).where(
                Draw.lottery_id == lottery_id,
                Draw.draw_number == draw_number,
            )
        )

    def get_with_numbers(self, id: int) -> Draw | None:
        """Load one draw with its children eagerly (1 + 1 batch, never N+1)."""
        return self._session.scalar(
            select(Draw)
            .options(selectinload(Draw.numbers), selectinload(Draw.super_number))
            .where(Draw.id == id)
        )

    def list_draws(
        self,
        *,
        lottery_code: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        order: str = "desc",
        page: int = 1,
        page_size: int = 50,
        is_deleted: bool | None = None,
    ) -> list[Draw]:
        """Return a filtered, ordered page of draws with children preloaded.

        ``lottery_code`` resolves via a join to ``lottery.code`` (the ``?lottery=``
        API filter). ``is_deleted`` (when not ``None``) filters the soft-delete
        flag in SQL so pagination stays correct — the service owns the CD-05
        exclusion policy and always passes ``False`` for functional queries;
        ``None`` keeps the unfiltered behaviour for administrative/raw access.
        Only the requested page is loaded; children are fetched in one selectin
        batch per relationship — the SELECT count does not grow with the page
        size (scope item 8).
        """
        stmt = (
            select(Draw)
            .join(Draw.lottery)
            .options(
                contains_eager(Draw.lottery),
                selectinload(Draw.numbers),
                selectinload(Draw.super_number),
            )
        )
        if lottery_code is not None:
            stmt = stmt.where(Lottery.code == lottery_code)
        if date_from is not None:
            stmt = stmt.where(Draw.draw_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Draw.draw_date <= date_to)
        if is_deleted is not None:
            stmt = stmt.where(Draw.is_deleted.is_(is_deleted))

        order_column = Draw.draw_date.desc() if order == "desc" else Draw.draw_date.asc()
        stmt = stmt.order_by(order_column, Draw.id).offset((page - 1) * page_size).limit(page_size)
        return list(self._session.scalars(stmt).all())

    def upsert_draw(
        self,
        *,
        lottery_id: int,
        draw_number: int,
        draw_date: date,
        jackpot=None,
        winners=None,
        is_deleted: bool = False,
    ) -> Draw:
        """Idempotent create-or-return primitive (design, Req 4; scope item 7).

        Exists → return the existing row untouched (no error); absent → create.
        Safe for F2 per-batch retry semantics: a replayed batch returns the
        already-imported draw instead of raising a UNIQUE violation. The
        on-conflict behaviour lives entirely inside this repository; no dialect
        SQL leaks into services or the API.
        """
        existing = self.get_by_natural_key(lottery_id, draw_number)
        if existing is not None:
            return existing
        return self.create(
            {
                "lottery_id": lottery_id,
                "draw_number": draw_number,
                "draw_date": draw_date,
                "jackpot": jackpot,
                "winners": winners,
                "is_deleted": is_deleted,
            }
        )
