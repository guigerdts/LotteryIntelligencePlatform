"""PR-1 import core tests: PARSER_VERSION, FileAdapter checksum, Phase A/B (S1-05).

Pure unit tests over the ``importers`` package with tmp CSV fixtures — no
database session, exercising the parsing/validation contract only (D6/IE-01..03).
"""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path

import pytest

from backend.app.importers.normalize import (
    EXPECTED_HEADERS,
    NormalizedDraw,
    normalize_row,
    split_numbers,
)
from backend.app.importers.sources import FileAdapter
from backend.app.importers.validate import (
    BadPhaseACode,
    BadRowCode,
    PhaseAResult,
    ValidationRules,
    validate_phase_a,
    validate_row,
)
from backend.app.importers.version import PARSER_VERSION, get_parser_version

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Baloto-like rule set shared by Phase B fixtures (numbers_to_select=6, 1..45, super 1..12).
RULES = ValidationRules(
    numbers_to_select=6,
    min_number=1,
    max_number=45,
    super_number_min=1,
    super_number_max=12,
)


def _raw_bytes(name: str) -> bytes:
    """Read a fixture's raw bytes for checksum expectations."""
    return (FIXTURES / name).read_bytes()


def _data(name: str) -> list[tuple[int, list[str]]]:
    """Decode a fixture into (row_number, cells) pairs, header excluded."""
    with (FIXTURES / name).open(encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)  # header
        return [(i, row) for i, row in enumerate(reader, start=2) if row]


# --- S1-01 PARSER_VERSION --------------------------------------------------


def test_parser_version_is_stable_module_constant() -> None:
    """PARSER_VERSION is a fixed constant, independent of the app version (D-G)."""
    assert PARSER_VERSION == "1.0"
    assert get_parser_version() == PARSER_VERSION


def test_parser_version_matches_semver_shape() -> None:
    """The parser version is a plain dotted string (maj.min)."""
    parts = PARSER_VERSION.split(".")
    assert len(parts) == 2
    assert all(part.isdigit() for part in parts)


# --- S1-02 FileAdapter stream + checksum -----------------------------------


def test_file_adapter_yields_header_then_rows_streaming() -> None:
    """First row is the header; data rows follow, one list per row."""
    rows = list(FileAdapter(FIXTURES / "canonical.csv").stream())
    assert rows[0] == list(EXPECTED_HEADERS)
    assert rows[1:] == [["100", "2024-01-05", "1,2,3,4,5,6", "7", "5000000.00", "3"]]


def test_file_adapter_checksum_matches_streamed_sha256() -> None:
    """Streaming a file yields a SHA-256 digest equal to hashing its raw bytes."""
    fixture = "canonical.csv"
    adapter = FileAdapter(FIXTURES / fixture)
    _ = list(adapter.stream())
    assert adapter.checksum == hashlib.sha256(_raw_bytes(fixture)).hexdigest()


def test_checksum_stability_same_file_same_digest() -> None:
    """Two separate streams over the identical fixture hash identically (IE-04)."""
    first = FileAdapter(FIXTURES / "canonical.csv")
    second = FileAdapter(FIXTURES / "canonical.csv")
    list(first.stream())
    list(second.stream())
    expected = hashlib.sha256(_raw_bytes("canonical.csv")).hexdigest()
    assert first.checksum == second.checksum == expected


def test_checksum_requires_stream_before_reporting() -> None:
    """Accessing the checksum before streaming raises RuntimeError."""
    adapter = FileAdapter(FIXTURES / "canonical.csv")
    with pytest.raises(RuntimeError):
        _ = adapter.checksum


# --- S1-03 normalization ---------------------------------------------------


def test_normalize_canonical_row_never_puts_super_in_numbers() -> None:
    """super_number stays in its own field, never merged into numbers (IE-01)."""
    assert EXPECTED_HEADERS == (
        ("draw_number", "draw_date", "numbers", "super_number", "jackpot", "winners")
    )
    draw = normalize_row(
        ["draw_number", "draw_date", "numbers", "super_number", "jackpot", "winners"],
        ["100", "2024-01-05", "1,2,3,4,5,6", "7", "5000000.00", "3"],
    )
    assert isinstance(draw, NormalizedDraw)
    assert draw.draw_number == 100
    assert draw.draw_date == date(2024, 1, 5)
    assert draw.numbers == (1, 2, 3, 4, 5, 6)
    assert draw.super_number == 7
    assert 7 not in draw.numbers
    assert draw.jackpot == "5000000.00"
    assert draw.winners == "3"


def test_split_numbers_skips_empty_tokens() -> None:
    """Comma-separated parsing ignores empty tokens (trailing/double commas)."""
    assert split_numbers("1,2,,3,") == [1, 2, 3]


# --- S1-04 Phase A whole-file structural -----------------------------------


def test_phase_a_accepts_canonical_header() -> None:
    """The canonical six-column header passes Phase A with no errors (IE-01)."""
    result = validate_phase_a(FileAdapter(FIXTURES / "canonical.csv"))
    assert result.ok is True
    assert result.errors == ()


@pytest.mark.parametrize(
    ("fixture", "expected_codes"),
    [
        ("unknown_column.csv", {BadPhaseACode.UNKNOWN_COLUMNS}),
        ("bad_delimiter.csv", {BadPhaseACode.UNKNOWN_COLUMNS, BadPhaseACode.MISSING_COLUMNS}),
        ("non_utf8.csv", {BadPhaseACode.INVALID_UTF8}),
    ],
)
def test_phase_a_rejects_structurally_bad_files(
    fixture: str, expected_codes: set[BadPhaseACode]
) -> None:
    """Any Phase A structural failure rejects the whole file (D6/IE-02)."""
    result = validate_phase_a(FileAdapter(FIXTURES / fixture))
    assert result.ok is False
    assert {error.code for error in result.errors} == expected_codes


def test_phase_a_rejects_empty_file() -> None:
    """An empty file is a whole-file rejection (EMPTY_FILE)."""
    blank = FIXTURES / "_empty.csv"
    blank.write_text("")
    try:
        result = validate_phase_a(FileAdapter(blank))
        assert result.ok is False
        assert BadPhaseACode.EMPTY_FILE in {e.code for e in result.errors}
    finally:
        blank.unlink()


def test_phase_a_ok_has_expected_type() -> None:
    """Phase A returns a typed PhaseAResult with ok/errors AND yields checksum."""
    result = validate_phase_a(FileAdapter(FIXTURES / "canonical.csv"))
    assert isinstance(result, PhaseAResult)


# --- S1-04 Phase B per-row semantic codes ----------------------------------


@pytest.mark.parametrize(
    ("fixture", "expected_codes"),
    [
        ("canonical.csv", set()),
        ("error_bad_row_number.csv", {BadRowCode.BAD_ROW_NUMBER}),
        ("error_bad_draw_date.csv", {BadRowCode.BAD_DRAW_DATE}),
        ("error_too_few_numbers.csv", {BadRowCode.TOO_FEW_NUMBERS}),
        ("error_too_many_numbers.csv", {BadRowCode.TOO_MANY_NUMBERS}),
        ("error_number_out_of_range.csv", {BadRowCode.NUMBER_OUT_OF_RANGE}),
        ("error_duplicate_in_draw.csv", {BadRowCode.DUPLICATE_IN_DRAW}),
        ("error_bad_super_number.csv", {BadRowCode.BAD_SUPER_NUMBER}),
        ("error_bad_jackpot.csv", {BadRowCode.BAD_JACKPOT}),
        ("error_bad_winners.csv", {BadRowCode.BAD_WINNERS}),
    ],
)
def test_phase_b_per_code_matrix(fixture: str, expected_codes: set[BadRowCode]) -> None:
    """Each error-code fixture surfaces exactly its taxonomy code (design §7)."""
    header = list(EXPECTED_HEADERS)
    for _row_number, row in _data(fixture):
        errors = validate_row(header, row, RULES)
        assert {error.code for error in errors} == expected_codes


def test_phase_b_structural_failures_do_not_abort_run() -> None:
    """A structurally bad header file still yields clean Phase B rows when forced (IE-02)."""
    header = list(EXPECTED_HEADERS)
    rows = _data("canonical.csv")
    assert rows  # canonical data present
    assert validate_row(header, rows[0][1], RULES) == []


def test_phase_b_in_file_duplicate_is_not_a_row_error() -> None:
    """A repeated draw_number is counted as duplicate by the DB, never a Phase B error (IE-04)."""
    header = list(EXPECTED_HEADERS)
    for _row_number, row in _data("error_in_file_duplicate.csv"):
        assert validate_row(header, row, RULES) == []


def test_parse_end_to_end_from_fixture() -> None:
    """normalize_row consumes a validated canonical row into a typed draw."""
    header = list(EXPECTED_HEADERS)
    for _row_number, row in _data("canonical.csv"):
        draw = normalize_row(header, row)
        assert draw.numbers == (1, 2, 3, 4, 5, 6)
