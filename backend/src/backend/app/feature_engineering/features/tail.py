"""Tail/series features depending on the whole draw series (FE-08..FE-10).

Pure functions over the ordered series ``ctx.draws``: repeated-from-previous
(FE-08), max current gap (FE-09), and current frequency (FE-10). All use the
``draw_number`` axis (FES-03) and exact INTEGER accumulators (FES-05).
"""

from __future__ import annotations

from collections import Counter

from backend.app.feature_engineering.context import FeatureContext


def repeated_from_previous(ctx: FeatureContext) -> int:
    """FE-08: count numbers matching the immediately previous draw's numbers.

    Scenario FE-08: draw 10 == ``[3, 9, 44]``, previous draw 9 == ``[3, 7, 44]`` ->
    ``2`` (3 and 44). Pure integer; the first draw has no previous so yields 0.
    """
    if len(ctx.draws) < 2:
        return 0
    prev = ctx.draws[-2].numbers
    prev_set = set(prev)
    return sum(1 for n in ctx.draw.numbers if n in prev_set)


def max_current_gap(ctx: FeatureContext) -> int:
    """FE-09: max gap (draw_number units) since each number last appeared.

    Scenario FE-09: a number never appeared by draw 12 -> gap measured from the first
    draw (12 - 1 = 11), the largest in the series. Uses the series order, never date.
    Every number in the rule universe ``[min, max]`` is considered; a never-seen number
    contributes its distance from the first draw, which dominates the max.
    """
    if not ctx.draws or ctx.rules is None:
        return 0
    current = ctx.draws[-1].draw_number
    first = ctx.draws[0].draw_number
    last_seen: dict[int, int] = {}
    for draw in ctx.draws:
        for n in draw.numbers:
            last_seen[n] = draw.draw_number
    max_gap = 0
    for n in range(ctx.rules.min_number, ctx.rules.max_number + 1):
        seen_at = last_seen.get(n)
        if seen_at is None:
            # Never appeared: distance measured from before the first draw.
            gap = current - first
        else:
            gap = current - seen_at
        max_gap = max(max_gap, gap)
    return max_gap


def current_frequency(ctx: FeatureContext) -> dict[int, int]:
    """FE-10: per-number occurrence count over the draw_number-ordered series.

    Scenario FE-10: number 7 appearing in draws 1, 4, 9 -> ``current_frequency[7] == 3``
    at draw 9. Deterministic mapping, integer counts (FES-05).
    """
    counts: Counter[int] = Counter()
    for draw in ctx.draws:
        for n in draw.numbers:
            counts[n] += 1
    return dict(counts.items())
