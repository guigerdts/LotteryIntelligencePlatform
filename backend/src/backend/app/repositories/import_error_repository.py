"""Import error repository: batch persistence of per-row Phase B failures (IE-03).

Rows rejected by Phase B are batched into ``import_errors`` via ``add_many`` and
flushed per commit window — never per-row (design §8 N+1). No orchestration.
"""

from __future__ import annotations

from backend.app.models import ImportError
from backend.app.repositories.base_repository import BaseRepository


class ImportErrorRepository(BaseRepository[ImportError]):
    """CRUD over the DI session for ``import_errors`` rows."""

    model = ImportError

    def add_many(self, import_id: int, errors: list[dict]) -> list[ImportError]:
        """Batch-insert Phase B error rows for a run (never per-row flush).

        Each ``errors`` entry carries row_number/draw_number/message/error_code/
        raw_row (IE-03); FK not-null ties every row to ``import_id``. The single
        flush surfaces any unexpected constraint failure at once.
        """
        instances = [ImportError(import_id=import_id, **error) for error in errors]
        self._session.add_all(instances)
        self._flush(operation="create")
        return instances
