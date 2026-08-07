"""Pure data carriers and the FeatureContext handed to feature ``compute`` (FES-06).

These are the compositional-root read structures the engine consumes: an ordered
``DrawRow`` (``draw_number`` axis, never ``draw_date``), the immutable lottery rules,
and the ``FeatureContext`` passed to every pure ``compute(ctx)``. No module here may
import ``models``/``statistics``/``repositories`` — the engine depends only on these
carriers (FES-06, design §4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DrawRow:
    """One draw on the official ``draw_number`` axis (FES-03).

    ``numbers`` are the raw drawn main values in ascending ``position`` order, already
    deterministically ordered by the provider (design §9 ORDER BY). Never carries
    ``draw_date`` ordering semantics — the axis is always ``draw_number``.
    """

    draw_number: int
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class LotteryRules:
    """Immutable lottery rule set needed by Core-Domain features (CD-01)."""

    min_number: int
    max_number: int
    numbers_to_select: int


@dataclass(frozen=True)
class FeatureContext:
    """Everything a pure feature ``compute`` needs, ready and deterministically ordered.

    ``draw`` is the current draw; ``draws`` is the full ordered series the engine was
    given (used by windowed/tail features such as ``repeated_from_previous``,
    ``max_current_gap`` and ``current_frequency``); ``rules`` carries the lottery rule
    derived mid-bands. ``params`` are the frozen feature params (part of the input
    fingerprint). All arithmetic that can reach a checksum must stay INTEGER/Decimal.
    """

    draw: DrawRow
    draws: tuple[DrawRow, ...] = field(default_factory=tuple)
    rules: LotteryRules | None = None
    params: Mapping[str, object] = field(default_factory=dict)
