"""Lottery repository: CRUD plus the ``code`` natural-key lookup (CD-01)."""

from __future__ import annotations

from sqlalchemy import select

from backend.app.models import Lottery
from backend.app.repositories.base_repository import BaseRepository


class LotteryRepository(BaseRepository[Lottery]):
    """CRUD over the DI session for ``lottery`` rows; natural key = ``code``."""

    model = Lottery

    def get_by_code(self, code: str) -> Lottery | None:
        """Look up a lottery by its natural key ``code`` (UNIQUE, idempotent imports)."""
        return self._session.scalar(select(Lottery).where(Lottery.code == code))
