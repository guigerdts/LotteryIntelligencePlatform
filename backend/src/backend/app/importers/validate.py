"""Two-phase CSV validation: Phase A structural (whole file) + Phase B per row (D6)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from backend.app.importers.normalize import EXPECTED_HEADERS
from backend.app.importers.sources import FileAdapter

_YYYY_MM_DD = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BadRowCode(StrEnum):
    """The nine Phase B per-row error codes (design §7, IE-03)."""

    BAD_ROW_NUMBER = "bad_row_number"
    BAD_DRAW_DATE = "bad_draw_date"
    TOO_FEW_NUMBERS = "too_few_numbers"
    TOO_MANY_NUMBERS = "too_many_numbers"
    NUMBER_OUT_OF_RANGE = "number_out_of_range"
    DUPLICATE_IN_DRAW = "duplicate_in_draw"
    BAD_SUPER_NUMBER = "bad_super_number"
    BAD_JACKPOT = "bad_jackpot"
    BAD_WINNERS = "bad_winners"


class BadPhaseACode(StrEnum):
    """Phase A whole-file structural codes (IE-02/D6)."""

    EMPTY_FILE = "empty_file"
    INVALID_UTF8 = "invalid_utf8"
    MISSING_COLUMNS = "missing_columns"
    UNKNOWN_COLUMNS = "unknown_columns"


@dataclass(frozen=True)
class ValidationRules:
    """Validated draw-rule parameters a lottery contributes to Phase B (CD-01).

    Pure configuration for row validation; values mirror the persisted lottery
    rule columns (``numbers_to_select``, ``min_number``/``max_number``, and the
    optional super range) without any database lookup here.
    """

    numbers_to_select: int
    min_number: int
    max_number: int
    super_number_min: int | None = None
    super_number_max: int | None = None

    @property
    def has_super_range(self) -> bool:
        """True when the lottery defines a usable super number range."""
        return self.super_number_min is not None and self.super_number_max is not None


@dataclass(frozen=True)
class PhaseAError:
    """A Phase A whole-file rejection reason (code plus explanatory message)."""

    code: BadPhaseACode
    message: str


@dataclass(frozen=True)
class PhaseAResult:
    """Outcome of Phase A structural validation for an entire file.

    ``ok`` is False when ANY structural condition fails, in which case the whole
    file MUST be rejected (D6/IE-02) and nothing imported.
    """

    ok: bool
    errors: tuple[PhaseAError, ...] = ()


@dataclass(frozen=True)
class RowValidationError:
    """A per-row Phase B error: taxonomy code plus message (IE-03)."""

    code: BadRowCode
    message: str


def validate_phase_a(adapter: FileAdapter) -> PhaseAResult:
    """Structurally validate a CSV file BEFORE any row processing (Phase A, D6).

    Drains the whole stream so a non-UTF-8 byte anywhere rejects the entire
    file (IE-02). Checks, in order: empty file, UTF-8 validity, delimiter/
    header contract (required columns present, no unknown columns, canonical
    order). On any failure the file is rejected wholesale — nothing is imported.
    """
    rows = adapter.stream()
    try:
        header = next(rows, None)
        if header is None:
            return PhaseAResult(
                ok=False,
                errors=(PhaseAError(BadPhaseACode.EMPTY_FILE, "file is empty"),),
            )
        for _ in rows:  # drain to prove the whole file decodes as UTF-8
            pass
    except UnicodeDecodeError as exc:
        reason = f"file is not valid UTF-8 ({exc})"
        return PhaseAResult(ok=False, errors=(PhaseAError(BadPhaseACode.INVALID_UTF8, reason),))

    header_errors = _check_header(header)
    if header_errors:
        return PhaseAResult(ok=False, errors=tuple(header_errors))
    return PhaseAResult(ok=True)


def validate_row(
    header: Sequence[str],
    row: Sequence[str],
    rules: ValidationRules,
) -> list[RowValidationError]:
    """Validate one data row semantically (Phase B, D6). Pure, no DB.

    Reports every problem found for the row as a :class:`RowValidationError`
    per the nine-code taxonomy of design §7. A caller records the row to
    ``import_errors`` and continues — an invalid row never aborts the run.
    """
    cells = {name: (row[i] if i < len(row) else "") for i, name in enumerate(header)}
    errors: list[RowValidationError] = []

    errors.extend(_validate_row_number(cells.get("draw_number", "")))
    errors.extend(_validate_draw_date(cells.get("draw_date", "")))
    errors.extend(_validate_numbers(cells.get("numbers", ""), rules))
    errors.extend(_validate_super_number(cells.get("super_number", ""), rules))
    errors.extend(_validate_decimal_field(cells.get("jackpot", ""), BadRowCode.BAD_JACKPOT))
    errors.extend(_validate_non_negative_int(cells.get("winners", ""), BadRowCode.BAD_WINNERS))

    return errors


# --- header screening ------------------------------------------------------


def _check_header(header: Sequence[str]) -> list[PhaseAError]:
    """Compare the CSV header against the canonical six-column contract (IE-01/D2).

    The header must be exactly the canonical column names, in order: every
    expected column present (no fewer), and no unknown columns (no extra). Both
    are structural whole-file failures.
    """
    header_names = tuple(str(cell).strip().lower() for cell in header)
    expected = tuple(name.lower() for name in EXPECTED_HEADERS)

    if header_names == expected:
        return []

    errors: list[PhaseAError] = []
    missing = [name for name in expected if name not in header_names]
    if missing:
        errors.append(
            PhaseAError(
                BadPhaseACode.MISSING_COLUMNS,
                f"header is missing required columns: {', '.join(missing)}",
            )
        )
    unknown = [name for name in header_names if name not in expected]
    if unknown:
        errors.append(
            PhaseAError(
                BadPhaseACode.UNKNOWN_COLUMNS,
                f"header contains unknown columns: {', '.join(unknown)}",
            )
        )
    fallback = [
        PhaseAError(BadPhaseACode.UNKNOWN_COLUMNS, "header does not match the canonical order")
    ]
    return errors or fallback


# --- Phase B field checks --------------------------------------------------


def _validate_row_number(cell: str) -> list[RowValidationError]:
    """Phase B ``bad_row_number``: missing, not int, or not > 0."""
    raw = cell.strip()
    if not raw.isdigit() or int(raw) <= 0:
        return [RowValidationError(BadRowCode.BAD_ROW_NUMBER, f"invalid draw_number {cell!r}")]
    return []


def _validate_draw_date(cell: str) -> list[RowValidationError]:
    """Phase B ``bad_draw_date``: not strict YYYY-MM-DD, or not a calendar date."""
    raw = cell.strip()
    if not _YYYY_MM_DD.match(raw):
        return [RowValidationError(BadRowCode.BAD_DRAW_DATE, f"invalid draw_date {cell!r}")]
    try:
        date.fromisoformat(raw)
    except ValueError:
        return [RowValidationError(BadRowCode.BAD_DRAW_DATE, f"invalid draw_date {cell!r}")]
    return []


def _validate_numbers(cell: str, rules: ValidationRules) -> list[RowValidationError]:
    """Phase B number checks: count/in-range/duplicates (IE-03, design §7)."""
    errors: list[RowValidationError] = []
    tokens = [token for token in (part.strip() for part in cell.split(",")) if token]
    values: list[int] = []
    for token in tokens:
        if not token.isdigit():
            errors.append(
                RowValidationError(BadRowCode.NUMBER_OUT_OF_RANGE, f"non-integer number {token!r}")
            )
            continue
        value = int(token)
        values.append(value)
        if value < rules.min_number or value > rules.max_number:
            errors.append(
                RowValidationError(
                    BadRowCode.NUMBER_OUT_OF_RANGE,
                    f"number {value} outside [{rules.min_number}, {rules.max_number}]",
                )
            )
    if len(values) < rules.numbers_to_select:
        errors.append(
            RowValidationError(
                BadRowCode.TOO_FEW_NUMBERS,
                f"{len(values)} numbers < {rules.numbers_to_select} required",
            )
        )
    elif len(values) > rules.numbers_to_select:
        errors.append(
            RowValidationError(
                BadRowCode.TOO_MANY_NUMBERS,
                f"{len(values)} numbers > {rules.numbers_to_select} required",
            )
        )
    if len(set(values)) != len(values):
        errors.append(
            RowValidationError(BadRowCode.DUPLICATE_IN_DRAW, "numbers repeat within the draw")
        )
    return errors


def _validate_super_number(cell: str, rules: ValidationRules) -> list[RowValidationError]:
    """Phase B ``bad_super_number``: out of the optional range or range undefined."""
    raw = cell.strip()
    if not raw:
        return []
    if not rules.has_super_range:
        return [RowValidationError(BadRowCode.BAD_SUPER_NUMBER, "lottery defines no super range")]
    if not raw.isdigit():
        return [
            RowValidationError(BadRowCode.BAD_SUPER_NUMBER, f"non-integer super_number {cell!r}")
        ]
    value = int(raw)
    if value < rules.super_number_min or value > rules.super_number_max:
        return [
            RowValidationError(
                BadRowCode.BAD_SUPER_NUMBER,
                f"super {value} outside [{rules.super_number_min}, {rules.super_number_max}]",
            )
        ]
    return []


def _validate_decimal_field(cell: str, code: BadRowCode) -> list[RowValidationError]:
    """Phase B optional decimal field (jackpot): valid decimal when present."""
    raw = cell.strip()
    if not raw:
        return []
    try:
        Decimal(raw)
    except InvalidOperation:
        return [RowValidationError(code, f"invalid decimal {cell!r}")]
    return []


def _validate_non_negative_int(cell: str, code: BadRowCode) -> list[RowValidationError]:
    """Phase B optional winners: non-negative integer when present."""
    raw = cell.strip()
    if not raw:
        return []
    if not raw.isdigit():
        return [RowValidationError(code, f"invalid integer {cell!r}")]
    return []
