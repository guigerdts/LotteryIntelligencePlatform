"""Import repository: create run, positional progress, conditional terminal transition (IE-06).

Persistence-only operations for the ``imports`` audit table. The create triggers
the new run, progress updates fold counters/``last_processed_row`` into the
per-draw transaction (D-D), and the conditional terminal UPDATE is the D-E
backstop: ``transition`` only flips the row when its current status matches the
expected one, and reports the rowcount so the service can detect an illegal
transition (terminal immutability) instead of racing ahead.
"""

from __future__ import annotations

from sqlalchemy import select, update

from backend.app.models import ImportJob
from backend.app.repositories.base_repository import BaseRepository


class ImportRepository(BaseRepository[ImportJob]):
    """CRUD over the DI session for ``imports`` + transition/lookup primitives."""

    model = ImportJob

    def create_run(self, data: dict) -> ImportJob:
        """Insert a new import run (status usually ``in_progress``)."""
        return self.create(data)

    def get_in_progress_for_lottery(self, lottery_id: int) -> ImportJob | None:
        """Return the most recent ``in_progress`` run for a lottery, or ``None``.

        The D-J concurrency pre-check: a NEW import for a lottery is rejected
        while one of its runs is still ``in_progress``. A ``partial`` run does
        not block (it is only resumed via the resume contract).
        """
        return self._session.scalar(
            select(ImportJob)
            .where(
                ImportJob.lottery_id == lottery_id,
                ImportJob.status == "in_progress",
            )
            .order_by(ImportJob.id.desc())
            .limit(1)
        )

    def get_resumable_run(
        self,
        *,
        lottery_id: int,
        checksum: str,
        parser_version: str,
        engine_version: str,
    ) -> ImportJob | None:
        """Return the most recent ``partial`` run matching the resume contract (D-D2).

        Resume is valid ONLY when a new attempt's ``checksum``,
        ``parser_version`` and ``engine_version`` match the target run for the
        same lottery — otherwise the attempt must start a fresh run. Terminal
        (completed/failed/rejected) runs are never returned here.
        """
        return self._session.scalar(
            select(ImportJob)
            .where(
                ImportJob.lottery_id == lottery_id,
                ImportJob.status == "partial",
                ImportJob.checksum == checksum,
                ImportJob.parser_version == parser_version,
                ImportJob.engine_version == engine_version,
            )
            .order_by(ImportJob.id.desc())
            .limit(1)
        )

    def transition(
        self,
        import_id: int,
        *,
        from_status: str,
        to_status: str,
        data: dict | None = None,
    ) -> bool:
        """Conditionally move a run from ``from_status`` to ``to_status``.

        Emits a single conditional UPDATE whose ``WHERE`` guards on the current
        status being exactly ``from_status``; returns whether a row changed. When
        it returns ``False`` the guard failed (e.g. a terminal row was targeted)
        and the caller raises a state-conflict error — the DB never allows a row
        to leave a terminal state (D-E backstop). ``data`` extras fold in with the
        status flip atomically.
        """
        values = {**(data or {}), "status": to_status}
        result = self._session.execute(
            update(ImportJob)
            .where(ImportJob.id == import_id, ImportJob.status == from_status)
            .values(**values)
        )
        return result.rowcount == 1

    def update_progress(self, import_id: int, data: dict) -> ImportJob | None:
        """Fold counters and/or ``last_processed_row`` into the open run (D-D)."""
        return self.update(import_id, data)
