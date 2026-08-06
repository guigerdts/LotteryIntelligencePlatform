"""DrawNumber repository: CRUD plus a batch insert primitive for draw children (CD-02)."""

from __future__ import annotations

from backend.app.models import DrawNumber
from backend.app.repositories.base_repository import BaseRepository


class DrawNumberRepository(BaseRepository[DrawNumber]):
    """CRUD over the DI session for ``draw_numbers`` rows."""

    model = DrawNumber

    def add_many(self, draw_id: int, numbers: list[int]) -> list[DrawNumber]:
        """Batch-insert the drawn numbers of a draw at 1-based positions.

        Pure persistence primitive (no validation — that is the F2 import / PR-3
        service). The flush surfaces ``UNIQUE(draw_id, position)`` and
        ``UNIQUE(draw_id, number)`` violations as ``DuplicateError`` so a bundle
        can be rolled back atomically by the service.
        """
        rows = [
            DrawNumber(draw_id=draw_id, position=position, number=number)
            for position, number in enumerate(numbers, start=1)
        ]
        self._session.add_all(rows)
        self._flush(operation="create")
        return rows
