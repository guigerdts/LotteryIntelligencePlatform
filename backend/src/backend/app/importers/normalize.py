"""CSV row normalization: typed in-memory draw containers, no DB (S1-03)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

# The canonical six-column CSV contract, in verbatim order (IE-01/D2). Phase A
# enforces this exact header; normalization relies on it.
EXPECTED_HEADERS: tuple[str, ...] = (
    "draw_number",
    "draw_date",
    "numbers",
    "super_number",
    "jackpot",
    "winners",
)


@dataclass(frozen=True)
class NormalizedDraw:
    """A typed, validated CSV row: one draw, normalized (IE-01/IE-03).

    ``numbers`` holds ONLY the main numbers: the ``super_number`` column lives in
    its own field and is never folded into ``numbers`` (F1 critical rule,
    IE-01). Optional ``jackpot``/``winners`` pass through as-is (raw cell
    strings) for later persistence.
    """

    draw_number: int
    draw_date: date
    numbers: tuple[int, ...]
    super_number: int | None
    jackpot: str | None
    winners: str | None


def split_numbers(cell: str) -> list[int]:
    """Split a comma-separated ``numbers`` cell into integers.

    Empty tokens (e.g. a trailing comma) are skipped; every surviving token is
    expected to be an integer — non-numeric tokens surface as validation errors
    in Phase B, so callers on the success path may assume integers.
    """
    return [int(token) for token in (part.strip() for part in cell.split(",")) if token]


def parse_draw_date(cell: str) -> date:
    """Parse a ``YYYY-MM-DD`` cell into a ``date`` (strict, calendar-valid).

    Raises ``ValueError`` for anything that is not an exact ``YYYY-MM-DD``
    calendar date; Phase B reports those as ``bad_draw_date`` before the
    success path ever reaches here.
    """
    return date.fromisoformat(cell.strip())


def _optional_int(cell: str) -> int | None:
    """Parse a cell into ``int`` when non-empty, else ``None`` (super_number)."""
    stripped = cell.strip()
    return int(stripped) if stripped else None


def normalize_row(header: Sequence[str], row: Sequence[str]) -> NormalizedDraw:
    """Normalize one validated CSV row into a :class:`NormalizedDraw`.

    Runs on the success path only (after Phase B accepted the row): parsing is
    strict and may raise ``ValueError``/``TypeError`` for a row that slipped
    through. ``super_number`` is never appended to ``numbers`` (IE-01);
    ``jackpot``/``winners`` are preserved as their raw strings.
    """
    cells: dict[str, str] = dict(zip(header, row, strict=False))
    return NormalizedDraw(
        draw_number=int(cells["draw_number"]),
        draw_date=parse_draw_date(cells["draw_date"]),
        numbers=tuple(split_numbers(cells["numbers"])),
        super_number=_optional_int(cells.get("super_number", "")),
        jackpot=(cells.get("jackpot") or "").strip() or None,
        winners=(cells.get("winners") or "").strip() or None,
    )
