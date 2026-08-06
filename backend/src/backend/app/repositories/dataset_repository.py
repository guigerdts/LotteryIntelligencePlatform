"""Dataset repository: CRUD over the DI session (no lock semantics — PR-3 service owns them)."""

from __future__ import annotations

from sqlalchemy import select

from backend.app.models import Dataset
from backend.app.repositories.base_repository import BaseRepository


class DatasetRepository(BaseRepository[Dataset]):
    """CRUD for ``datasets`` rows.

    ``create``/``list``/``get``/``update`` come from the generic base. Locking
    (``is_locked``) and immutability policy are domain-service concerns (PR-3);
    this repository provides no lock orchestration, only persistence primitives.
    """

    model = Dataset

    def get_by_version(self, version: str) -> Dataset | None:
        """Look up a dataset by its natural key ``version`` (UNIQUE, CD-03)."""
        return self._session.scalar(select(Dataset).where(Dataset.version == version))
