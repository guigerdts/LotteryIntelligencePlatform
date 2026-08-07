"""Generator identity, metric-set definitions, and fold/scope rules (design §8).

Pure, constant-only module: no imports from models/repositories/services, no DB.
``STATS_GENERATOR_VERSION`` is the algorithm identity compared in the snapshot
and its checksum (C1/STE-04); any change to metric meaning, rounding, or fold
order that alters a sum MUST bump it (design §8). ``SCOPE`` names the two
supported generation scopes and the fold rule each implies (STE-06/C4).
"""

from __future__ import annotations

from dataclasses import dataclass

# Bumped only when metric interpretation changes (requirements 8/STE-04): gap
# meaning, rounding mode, or fold order that changes a sum. NOT bumped on app
# deploy, engine version, dataset re-import, or non-semantic edits (design §8).
STATS_GENERATOR_VERSION = "1.0.0"

# The single supported metric bundle for this release. Selectable via the API/CLI
# ``metrics=["core"]``; the engine computes exactly these metric families.
CORE_METRICS: frozenset[str] = frozenset({"frequency", "positions", "gaps", "averages", "entropy"})


@dataclass(frozen=True)
class Scope:
    """A generation scope binding the fold rule it implies (design C4/STE-06)."""

    name: str
    # ``incremental`` folds the delta (draw_number > draws_to) into the active
    # snapshot's accumulators and never recomputes full history; ``full``
    # recomputes every metric from all draws into a NEW version (C1).
    incremental: bool


# Scope labels surfaced to the API/CLI (design §5/§6).
SCOPE_INCREMENTAL = Scope(name="incremental", incremental=True)
SCOPE_FULL = Scope(name="full", incremental=False)

SCOPES: dict[str, Scope] = {
    SCOPE_INCREMENTAL.name: SCOPE_INCREMENTAL,
    SCOPE_FULL.name: SCOPE_FULL,
}
