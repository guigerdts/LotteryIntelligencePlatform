"""Import use-case service: run lifecycle, state machine, resume, concurrency.

Implements ``run_import`` — the F2 import use case — and ``generate_dataset``,
the on-demand immutable dataset operator (D-A/D-D/D-D2/D-E/D-G/D-H/D-J plus
D5/IE-09). The service owns: the Phase A -> rejected terminal, creating the
audit run, the per-draw atomic loop (via
:class:`backend.app.importers.importer.DrawImporter`), counter reconciliation
(IE-06), the resume contract (D-D2), the concurrency pre-check (D-J), and — for
``generate_dataset`` — the filters -> batched selection -> SHA-256 checksum ->
immutable locked dataset contract (IE-09). All draw persistence is delegated
exclusively to ``DrawService.create_draw_bundle`` (user mandate) — no
draw/numbers/super writes happen here. Import NEVER creates a dataset: dataset
generation is an explicit, independent operation only (D5/IE-09).

No HTTP, no CLI, no request parsing (PR-3 owns the surface).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.config.settings import get_settings
from backend.app.importers.importer import DrawImporter, ImportCounters
from backend.app.importers.sources import FileAdapter
from backend.app.importers.validate import ValidationRules, validate_phase_a
from backend.app.importers.version import get_parser_version
from backend.app.models import Dataset
from backend.app.repositories.draw_repository import DrawRepository
from backend.app.repositories.import_repository import ImportRepository
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.dataset_service import DatasetService
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
        self._draws = DrawRepository(session)
        self._datasets = DatasetService(session)

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

    def generate_dataset(
        self,
        *,
        version: str,
        lottery_id: int,
        generator_version: str,
        filters: str | None = None,
        description: str | None = None,
    ) -> Dataset:
        """Generate an immutable, locked dataset on demand (D5/IE-09).

        Contract: ``filters -> selection -> checksum -> generator_version ->
        immutable -> lock``. The draws are selected in ONE batched query
        (``is_deleted=False`` plus the optional date window), the SHA-256 checksum
        is computed over the canonical ``{filters, generator_version, draw_ids}``
        (stable ordering → stable checksum), and the row is created via
        ``DatasetService.create_dataset`` with that checksum and ``is_locked=True``
        — immutability and the lock are DatasetService-owned (CD-03). Import
        itself NEVER creates a dataset: this operation is explicit and independent.

        An unknown ``lottery_id`` maps to ``NotFoundError`` (RESOURCE_NOT_FOUND,
        404); an already-used ``version`` maps to ``DuplicateError``
        (DUPLICATE_RESOURCE, 409); a malformed ``filters`` JSON or date raises
        ``ValidationError`` (422).
        """
        lottery = get_lottery_or_raise(self._lotteries, lottery_id)
        date_from, date_to = _parse_dataset_filters(filters)
        draw_ids = self._draws.list_dataset_draw_ids(
            lottery_id=lottery.id, date_from=date_from, date_to=date_to
        )
        checksum = _dataset_checksum(filters, generator_version, draw_ids)
        return self._datasets.create_dataset(
            version=version,
            lottery_id=lottery.id,
            generator_version=generator_version,
            draw_ids=draw_ids,
            description=description,
            filters=filters,
            checksum=checksum,
        )

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


# --- dataset generation helpers (D5/IE-09) ---------------------------------


def _dataset_checksum(
    filters: str | None, generator_version: str, draw_ids: list[int]
) -> str:
    """SHA-256 over the canonical ``{filters, generator_version, draw_ids}``.

    ``sort_keys`` + compact separators give a deterministic serialization so any
    two generations over the same content produce an identical checksum (CD-03 —
    the checksum depends only on dataset content and algorithm, IE-09).
    """
    canonical = json.dumps(
        {"filters": filters, "generator_version": generator_version, "draw_ids": draw_ids},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _parse_dataset_filters(filters: str | None) -> tuple[date | None, date | None]:
    """Parse the optional JSON ``filters`` into a ``(date_from, date_to)`` window.

    Only ``date_from`` and ``date_to`` keys are supported; any other key or a
    malformed JSON/date raises ``ValidationError`` (422). The raw ``filters``
    string is preserved verbatim on the dataset row (CD-03), so parsing here does
    not change what is recorded.
    """
    if not filters:
        return None, None
    try:
        raw = json.loads(filters)
    except json.JSONDecodeError as exc:
        raise ValidationError("dataset filters must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValidationError("dataset filters must be a JSON object")
    unknown = set(raw) - {"date_from", "date_to"}
    if unknown:
        raise ValidationError(f"unknown dataset filter keys: {sorted(unknown)}")
    date_from = _parse_dataset_date("date_from", raw.get("date_from"))
    date_to = _parse_dataset_date("date_to", raw.get("date_to"))
    return date_from, date_to


def _parse_dataset_date(key: str, value) -> date | None:
    """Parse a ``YYYY-MM-DD`` filter value; ``None`` passes through unchanged."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"dataset filter {key} must be a YYYY-MM-DD string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"dataset filter {key} must be a YYYY-MM-DD date") from exc
