"""SuperNumber repository: CRUD over the DI session for the 0..1 super number (CD-02)."""

from __future__ import annotations

from backend.app.models import SuperNumber
from backend.app.repositories.base_repository import BaseRepository


class SuperNumberRepository(BaseRepository[SuperNumber]):
    """CRUD over the DI session for ``super_number`` rows (UNIQUE(draw_id) enforces 0..1)."""

    model = SuperNumber

    def add(self, draw_id: int, value: int) -> SuperNumber:
        """Insert one super number for a draw; a second one surfaces ``DuplicateError``."""
        return self.create({"draw_id": draw_id, "value": value})
