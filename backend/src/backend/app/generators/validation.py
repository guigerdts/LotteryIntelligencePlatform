"""Validation module — GEN-006 lottery rules check.

Validates that a generated combination respects the lottery configuration:
distinct numbers, all in [min_number, max_number], sorted ascending, and a
REQUIRED super_number in [super_number_min, super_number_max] (R1/D5): a
missing Superbalota is always invalid.
"""

from __future__ import annotations

from typing import Protocol


class LotteryConfig(Protocol):
    """Minimal lottery configuration contract for validation."""

    @property
    def numbers_to_select(self) -> int: ...
    @property
    def min_number(self) -> int: ...
    @property
    def max_number(self) -> int: ...
    @property
    def super_number_min(self) -> int: ...
    @property
    def super_number_max(self) -> int: ...


def validate_combination(
    numbers: list[int],
    super_number: int | None,
    lottery_config: LotteryConfig,
) -> bool:
    """Check that a combination is valid per lottery rules (GEN-006, R1/D5).

    Rules:
      - Exactly ``numbers_to_select`` numbers.
      - All distinct.
      - All in ``[min_number, max_number]``.
      - Sorted ascending.
      - ``super_number`` present and in ``[super_number_min, super_number_max]``
        (a missing Superbalota is always invalid).

    Returns ``True`` if valid, ``False`` otherwise.
    """
    cfg = lottery_config

    # Exactly numbers_to_select numbers
    if len(numbers) != cfg.numbers_to_select:
        return False

    # All distinct
    if len(set(numbers)) != len(numbers):
        return False

    # All in [min_number, max_number]
    for n in numbers:
        if n < cfg.min_number or n > cfg.max_number:
            return False

    # Sorted ascending
    if numbers != sorted(numbers):
        return False

    # Super number REQUIRED and in range (D5: None no longer skips the check)
    if super_number is None:
        return False
    return cfg.super_number_min <= super_number <= cfg.super_number_max
