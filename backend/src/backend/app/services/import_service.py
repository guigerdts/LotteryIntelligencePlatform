"""Import use-case service: run lifecycle, state machine, resume, concurrency.

Implements ``run_import``, the F2 import use case (D-A/D-D/D-D2/D-E/D-G/D-H/D-J,
IE-02/04/05/06/07/10). The service owns: the Phase A -> rejected terminal,
creating the audit run, the per-draw atomic loop (via
:class:`backend.app.importers.importer.DrawImporter`), counter reconciliation
(IE-06), the resume contract (D-D2), and the concurrency pre-check (D-J). All
draw persistence is delegated exclusively to ``DrawService.create_draw_bundle``
(user mandate) — no draw/numbers/super writes happen here.

No HTTP, no CLI, no request parsing (PR-3 owns the surface).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.config.settings import get_settings
from backend.app.importers.importer import DrawImporter, ImportCounters
from backend.app.importers.sources import FileAdapter
from backend.app.importers.validate import ValidationRules, validate_phase_a
from backend.app.importers.version import get_parser_version
from backend.app.repositories.import_repository import ImportRepository
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import (
    ImportConflictError,
    ValidationError,
)
from backend.app.services.helpers import get_lottery_or_raise


class ImportService:
    """Import use cases over one DI session (state machine, resume, per-draw tx)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lotteries = LotteryRepository(session)
        self._imports = ImportRepository(session)

    def run_import(
        self,
        *,
        lottery_id: int,
        source_path: str | Path,
        import_type: str = "manual",
        started_by: str | None = None,
        resume: bool = False,
    ) -> dict:
        """Run (or resume) an import and return the audit summary (IE-04/06).

        Phase A structural failure -> create a ``rejected`` terminal run (0 draws)
        and raise ``ValidationError`` (IE-02). Otherwise create/resume the run,
        stream rows through the importer, and finish ``completed`` (fresh) or
        ``partial -> completed`` (resume). An unhandled row-loop failure marks the
        run terminal ``failed`` before propagating (D-E).

        Concurrency (D-J): a NEW run for a lottery is rejected with
        ``ImportConflictError`` while an ``in_progress`` run exists for it.
        Resume (D-D2): honored ONLY for a ``partial`` run whose ``checksum``,
        ``parser_version``, ``engine_version`` and ``lottery_id`` all match the
        new attempt; a terminal run or any mismatch starts a FRESH run — never
        resume a different file.
        """
        lottery = get_lottery_or_raise(self._lotteries, lottery_id)
        rules = self._lottery_rules(lottery)

        adapter = FileAdapter(source_path)
        phase_a = validate_phase_a(adapter)
        if not phase_a.ok:
            run = self._rejected_run(lottery_id, source_path, import_type, started_by)
            raise ValidationError(f"import rejected in Phase A: {phase_a.errors[0].code}")

        checksum = adapter.checksum
        engine_version = get_settings().app_version
        parser_version = get_parser_version()

        # Resume contract (D-D2): continue a `partial` run matching on every field.
        resumable = None
        if resume:
            resumable = self._imports.get_resumable_run(
                lottery_id=lottery_id,
                checksum=checksum,
                parser_version=parser_version,
                engine_version=engine_version,
            )

        if resumable is None:
            self._ensure_no_active_run(lottery_id)
            run = self._create_run(
                lottery_id=lottery_id,
                source_path=source_path,
                import_type=import_type,
                started_by=started_by,
                checksum=checksum,
                engine_version=engine_version,
                parser_version=parser_version,
                status="in_progress",
            )
            self._session.commit()
        else:
            run = resumable
            self._session.commit()

        # Fresh adapter re-streams the file for the row loop (Phase A drained one).
        stream = FileAdapter(source_path).stream()
        header = next(stream, None)
        if header is None:
            return self._finish(run, ImportCounters(total_rows=0), status="failed")

        importer = DrawImporter(
            session=self._session,
            lottery_id=lottery_id,
            rules=rules,
            run_id=run.id,
        )
        try:
            counters = importer.process(header, stream)
        except Exception:
            self._mark_failed(run)
            raise
        return self._finish(run, counters, status="completed")

    # --- lifecycle helpers -------------------------------------------------

    def _ensure_no_active_run(self, lottery_id: int) -> None:
        """D-J concurrency pre-check: at most one ``in_progress`` run per lottery."""
        if self._imports.get_in_progress_for_lottery(lottery_id) is not None:
            raise ImportConflictError(f"lottery {lottery_id} already has an in-progress import run")

    def _create_run(
        self,
        *,
        lottery_id: int,
        source_path,
        import_type: str,
        started_by: str | None,
        checksum: str,
        engine_version: str,
        parser_version: str,
        status: str,
    ):
        """Insert one ``imports`` row with zeroed counters and tz-aware timestamps."""
        now = datetime.now(UTC)
        return self._imports.create_run(
            {
                "lottery_id": lottery_id,
                "status": status,
                "source_file": str(source_path),
                "checksum": checksum,
                "import_type": import_type,
                "started_by": started_by,
                "engine_version": engine_version,
                "parser_version": parser_version,
                "total_rows": 0,
                "imported_rows": 0,
                "skipped_rows": 0,
                "duplicate_rows": 0,
                "error_rows": 0,
                "duration_ms": 0,
                "started_at": now,
                "finished_at": now,
                "last_processed_row": None,
            }
        )

    def _rejected_run(self, lottery_id: int, source_path, import_type, started_by):
        """Phase A failure: create ``in_progress`` then flip to terminal ``rejected``.

        The row persists so the audit never loses the execution (IE-02); the
        conditional-terminal transition (D-E) makes the flip race-safe.
        """
        run = self._create_run(
            lottery_id=lottery_id,
            source_path=source_path,
            import_type=import_type,
            started_by=started_by,
            checksum=_checksum_of(source_path),
            engine_version=get_settings().app_version,
            parser_version=get_parser_version(),
            status="in_progress",
        )
        self._session.commit()  # persist the in-progress row first
        self._imports.transition(run.id, from_status="in_progress", to_status="rejected")
        self._session.commit()
        return run

    def _finish(self, run, counters: ImportCounters, *, status: str) -> dict:
        """Terminal transition + counters into the audit summary (IE-04/06)."""
        finished_at = datetime.now(UTC)
        data = {
            "status": status,
            "finished_at": finished_at,
            "duration_ms": int((finished_at - run.started_at).total_seconds() * 1000),
            "total_rows": counters.total_rows,
            "imported_rows": counters.imported_rows,
            "skipped_rows": counters.skipped_rows,
            "duplicate_rows": counters.duplicate_rows,
            "error_rows": counters.error_rows,
            "last_processed_row": counters.last_processed_row,
        }
        transition = self._imports.transition(
            run.id, from_status=run.status, to_status=status, data=data
        )
        if not transition:
            raise RuntimeError(f"cannot transition run {run.id} to {status}")
        self._session.commit()
        self._session.refresh(run)
        return {
            "id": run.id,
            "status": run.status,
            "total_rows": run.total_rows,
            "imported_rows": run.imported_rows,
            "skipped_rows": run.skipped_rows,
            "duplicate_rows": run.duplicate_rows,
            "error_rows": run.error_rows,
            "duration_ms": run.duration_ms,
            "checksum": run.checksum,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }

    def _mark_failed(self, run) -> None:
        """Flip any non-terminal run to terminal ``failed`` (D-E, crash path)."""
        if run.status in {"completed", "failed", "rejected"}:
            return
        try:
            now = datetime.now(UTC)
            self._imports.transition(
                run.id,
                from_status=run.status,
                to_status="failed",
                data={
                    "finished_at": now,
                    "duration_ms": int((now - run.started_at).total_seconds() * 1000),
                },
            )
            self._session.commit()
        except Exception:
            self._session.rollback()

    def _lottery_rules(self, lottery) -> ValidationRules:
        """Phase-B rules mirrored from the lottery's persisted columns (CD-01)."""
        return ValidationRules(
            numbers_to_select=lottery.numbers_to_select,
            min_number=lottery.min_number,
            max_number=lottery.max_number,
            super_number_min=lottery.super_number_min,
            super_number_max=lottery.super_number_max,
        )


def _checksum_of(source_path) -> str:
    """Best-effort SHA-256 of the source file for a rejected-run audit row."""
    adapter = FileAdapter(source_path)
    list(adapter.stream())
    return adapter.checksum
