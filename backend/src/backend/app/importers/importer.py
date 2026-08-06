"""Import orchestration: stream-parse rows and commit each draw atomically (D-A/D-D).

Pure orchestrator that runs the row loop of an import: for every CSV data row it
applies Phase B, classifies it as imported / duplicate / skipped / error, and for
a new draw composes the F1 ``DrawService.create_draw_bundle`` — the ONLY
persistence path for draws/numbers/super (user mandate). Counters and
``last_processed_row`` are folded into the SAME transaction that commits the
draw (design D-D), so a crash can never leave the audit counters ahead of the
committed draws; resume continues from ``last_processed_row + 1`` and committed
draws are never re-imported or miscounted as duplicates.

``import_type`` / ``engine_version`` / ``parser_version`` / ``started_by`` are
recorded by the caller service; this module owns the classification loop only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.importers.normalize import normalize_row
from backend.app.importers.validate import ValidationRules, validate_row
from backend.app.repositories.draw_repository import DrawRepository
from backend.app.repositories.errors import DuplicateError
from backend.app.repositories.import_error_repository import ImportErrorRepository
from backend.app.repositories.import_repository import ImportRepository
from backend.app.services.draw_service import DrawService


@dataclass
class ImportCounters:
    """Row-classification counters for one run (IE-06 reconcile)."""

    total_rows: int = 0
    imported_rows: int = 0
    skipped_rows: int = 0
    duplicate_rows: int = 0
    error_rows: int = 0
    last_processed_row: int | None = None

    @property
    def reconciled(self) -> bool:
        """True when ``total = imported + skipped + duplicate + error`` (IE-06)."""
        return self.total_rows == (
            self.imported_rows + self.skipped_rows + self.duplicate_rows + self.error_rows
        )


class DrawImporter:
    """Streams one CSV through Phase B and commits one draw per transaction."""

    def __init__(
        self,
        *,
        session: Session,
        lottery_id: int,
        rules: ValidationRules,
        run_id: int,
    ) -> None:
        self._session = session
        self._lottery_id = lottery_id
        self._rules = rules
        self._run_id = run_id
        self._imports = ImportRepository(session)
        self._draws = DrawRepository(session)
        self._errors = ImportErrorRepository(session)
        self._draw_service = DrawService(session)

    def process(self, header: Sequence[str], rows) -> ImportCounters:
        """Consume data ``rows`` and return the final counter state.

        ``rows`` is the CSV data stream (header already read). Every new draw
        commits via ``create_draw_bundle`` with the counters and
        ``last_processed_row`` staged in the same transaction; duplicates and
        Phase B errors commit their counter delta separately. Per-row
        ``import_errors`` are batched into the commit windows (design §8).
        """
        counters = self._current_counters()
        pending_errors: list[dict] = []
        row_number = 2  # physical CSV row index (header = 1, first data = 2)

        for row in rows:
            # A resumed run skips rows already committed in a prior attempt.
            if (
                counters.last_processed_row is not None
                and row_number <= counters.last_processed_row
            ):
                row_number += 1
                continue

            counters.total_rows += 1

            validation = validate_row(header, row, self._rules)
            if validation:
                self._record_phase_b_errors(counters, row_number, row, validation, pending_errors)
                row_number += 1
                continue

            normalized = normalize_row(header, row)
            jackpot = Decimal(normalized.jackpot) if normalized.jackpot is not None else None
            winners = int(normalized.winners) if normalized.winners is not None else None

            if self._draws.get_by_natural_key(self._lottery_id, normalized.draw_number) is not None:
                counters.duplicate_rows += 1
                counters.last_processed_row = row_number
                self._commit_window(counters, pending_errors)
                row_number += 1
                continue

            counters.imported_rows += 1
            counters.last_processed_row = row_number
            # Stage counters into the in-session run BEFORE the draw commit so
            # create_draw_bundle's commit persists both together (D-D).
            self._imports.update_progress(self._run_id, self._counter_delta(counters))
            try:
                self._draw_service.create_draw_bundle(
                    lottery_id=self._lottery_id,
                    draw_number=normalized.draw_number,
                    draw_date=normalized.draw_date,
                    numbers=list(normalized.numbers),
                    super_number=normalized.super_number,
                    jackpot=jackpot,
                    winners=winners,
                )
            except DuplicateError:  # concurrent race: natural key landed between check and insert
                counters.imported_rows -= 1
                counters.duplicate_rows += 1
                self._commit_window(counters, pending_errors)
            row_number += 1

        self._commit_window(counters, pending_errors)
        return counters

    # --- private helpers ---------------------------------------------------

    def _current_counters(self) -> ImportCounters:
        """Seed counters from the run row so a resume carries forward (D-D2)."""
        run = self._imports.get(self._run_id)
        if run is None:
            raise RuntimeError("import run does not exist")
        return ImportCounters(
            total_rows=run.total_rows,
            imported_rows=run.imported_rows,
            skipped_rows=run.skipped_rows,
            duplicate_rows=run.duplicate_rows,
            error_rows=run.error_rows,
            last_processed_row=run.last_processed_row,
        )

    def _counter_delta(self, counters: ImportCounters) -> dict:
        """Map the condensed counters to run-column updates."""
        return {
            "total_rows": counters.total_rows,
            "imported_rows": counters.imported_rows,
            "skipped_rows": counters.skipped_rows,
            "duplicate_rows": counters.duplicate_rows,
            "error_rows": counters.error_rows,
            "last_processed_row": counters.last_processed_row,
        }

    def _record_phase_b_errors(
        self,
        counters: ImportCounters,
        row_number: int,
        row: Sequence[str],
        validation,
        pending_errors: list[dict],
    ) -> None:
        """Batch one ``import_errors`` row per Phase B failure and count the row (IE-03)."""
        pending_errors.extend(
            {
                "row_number": row_number,
                "draw_number": _raw_draw_number(row),
                "message": error.message,
                "error_code": error.code.value,
                "raw_row": ",".join(row),
            }
            for error in validation
        )
        counters.error_rows += 1
        counters.last_processed_row = row_number
        self._commit_window(counters, pending_errors)

    def _commit_window(self, counters: ImportCounters, pending_errors: list[dict]) -> None:
        """Flush a commit window: batched error rows + run-counters update + commit."""
        if pending_errors:
            self._errors.add_many(self._run_id, pending_errors)
            pending_errors.clear()
        self._imports.update_progress(self._run_id, self._counter_delta(counters))
        self._session.commit()


def _raw_draw_number(row: Sequence[str]) -> int | None:
    """Best-effort ``draw_number`` from the first cell; ``None`` when unparseable."""
    if not row:
        return None
    try:
        return int(row[0].strip())
    except ValueError:
        return None
