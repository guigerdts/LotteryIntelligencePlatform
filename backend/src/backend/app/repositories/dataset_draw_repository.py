"""DatasetDraw repository: composition primitives and batch draw loading.

The ``dataset_draws`` join is composed through this repository. Children are
loaded in bulk (one join query, then one IN query) so loading a dataset's draws
never degrades to N+1 (design N+1 table; scope item 8).
"""

from __future__ import annotations

from sqlalchemy import select

from backend.app.models import DatasetDraw, Draw
from backend.app.repositories.base_repository import BaseRepository


class DatasetDrawRepository(BaseRepository[DatasetDraw]):
    """CRUD + composition primitives for ``dataset_draws`` join rows."""

    model = DatasetDraw

    def add_many(self, *, dataset_id: int, draw_ids: list[int]) -> list[int]:
        """Batch-insert composition rows; ``UNIQUE(dataset_id, draw_id)`` surfaces
        duplicates as ``DuplicateError`` (service rolls back atomically)."""
        rows = [DatasetDraw(dataset_id=dataset_id, draw_id=draw_id) for draw_id in draw_ids]
        self._session.add_all(rows)
        self._flush(operation="create")
        return [row.id for row in rows]

    def draws_for_dataset(self, dataset_id: int) -> list[Draw]:
        """Return a dataset's draws in composition order using exactly two SELECTs.

        First query fetches the ordered join ``draw_id``s; the second loads the
        draw rows with a single ``IN`` predicate (batch load, no N+1).
        """
        draw_ids = list(
            self._session.scalars(
                select(DatasetDraw.draw_id)
                .where(DatasetDraw.dataset_id == dataset_id)
                .order_by(DatasetDraw.id)
            ).all()
        )
        if not draw_ids:
            return []
        rows = self._session.scalars(select(Draw).where(Draw.id.in_(draw_ids))).all()
        by_id = {draw.id: draw for draw in rows}
        return [by_id[draw_id] for draw_id in draw_ids]
