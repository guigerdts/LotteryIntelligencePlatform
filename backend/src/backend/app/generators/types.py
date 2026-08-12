"""Domain types for the Generator module.

Frozen dataclasses representing the core generation domain objects:
- GenerationConfig: pipeline input parameters (lottery_id, count, seed, selection_id)
- Combination: one generated lottery combination (position, numbers, super_number)
- Allocation: per-entry count allocation (entry_index, count)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """Immutable pipeline input for combination generation (GEN-001, GEN-009).

    Carries the lottery target, desired count, optional seed override, and
    the F12 selection to weight sampling from.
    """

    lottery_id: int
    count: int
    seed: int | None
    selection_id: int


@dataclass(frozen=True)
class Combination:
    """One generated lottery combination with position and optional super_number."""

    position: int
    numbers: list[int]
    super_number: int | None


@dataclass(frozen=True)
class Allocation:
    """Per-entry count allocation from the micro-unit integer rule (GEN-004)."""

    entry_index: int
    count: int
