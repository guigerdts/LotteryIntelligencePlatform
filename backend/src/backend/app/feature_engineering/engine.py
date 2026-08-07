"""Pure Feature Engine orchestrator (FES-08, design §1/§6) — no DB.

Executes the registry's runnable features in Kahn topological order over a given
deterministically-ordered set of ``DrawRow`` inputs and produces a deterministic
``feature_values`` mapping plus an input fingerprint (FES-05). It never imports a concrete
``statistics``/``models``/``repository`` implementation — inputs arrive ready through the
provider carriers (FES-06). A ``future-statistics`` feature is declared (registered +
versioned) yet never scheduled: it contributes no value here (FES-08 / GF2(b)).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from backend.app.feature_engineering.context import DrawRow, FeatureContext, LotteryRules
from backend.app.feature_engineering.fingerprint import feature_input_fingerprint
from backend.app.feature_engineering.registry import FeatureDefinition, FeatureRegistry


@dataclass(frozen=True)
class ExecutionResult:
    """One deterministic engine pass over a draw set.

    ``values`` maps ``feature_id -> {draw_number: value}`` (INTEGER/Decimal only; float
    never enters a checksum or a persisted value — FES-05). ``draw_numbers`` is the
    ordered ``draw_number`` axis. ``fingerprint`` is the canonical input SHA-256 (§5).
    """

    draws: tuple[DrawRow, ...]
    draw_numbers: tuple[int, ...]
    values: Mapping[str, Mapping[int, object]]
    fingerprint: str


class FeatureEngine:
    """Apply a ``FeatureRegistry`` to a pure draw set in deterministic topo order.

    The engine is deliberately stateless and side-effect-free: it accepts a registry and a
    list of ordered ``DrawRow``, returns the computed values + fingerprint. Persistence,
    budgets, versioning, and atomic transactions belong to the service layer (PR2).
    """

    def __init__(self, registry: FeatureRegistry) -> None:
        self._registry = registry

    def execute(
        self,
        draws: list[DrawRow] | tuple[DrawRow, ...],
        rules: LotteryRules | None = None,
        *,
        lottery_id: int = 0,
    ) -> ExecutionResult:
        # Official axis is draw_number (FES-03): explicit sort, never physical order.
        ordered = tuple(sorted(draws, key=lambda d: d.draw_number))
        draw_numbers = tuple(d.draw_number for d in ordered)

        run_ids = self._registry.iter_computable()

        values: dict[str, dict[int, object]] = {}
        for feature_id in run_ids:
            compute = self._registry.compute(feature_id)
            if compute is None:
                continue
            defn = self._registry.get(feature_id)
            series: dict[int, object] = {}
            for index, draw in enumerate(ordered):
                ctx = FeatureContext(
                    draw=draw,
                    draws=ordered[: index + 1],
                    rules=rules,
                    params=defn.params if defn is not None else {},
                )
                series[draw.draw_number] = compute(ctx)
            values[feature_id] = series

        input_payload = {
            "draws": {
                "lottery": lottery_id,
                "from": draw_numbers[0] if draw_numbers else 0,
                "to": draw_numbers[-1] if draw_numbers else 0,
                "checksum": _draw_set_checksum(ordered),
            },
            "features": sorted(
                (defn.id, defn.version, dict(defn.params))
                for defn in self._registry.definitions().values()
                if defn.id in run_ids
            ),
            "stats": None,
        }
        fingerprint = feature_input_fingerprint(input_payload)

        return ExecutionResult(
            draws=ordered,
            draw_numbers=draw_numbers,
            values=values,
            fingerprint=fingerprint,
        )


def _draw_set_checksum(draws: tuple[DrawRow, ...]) -> str:
    """Deterministic SHA-256 of the ordered draw rows (FES-05)."""
    ordered = [[d.draw_number, list(d.numbers)] for d in sorted(draws, key=lambda x: x.draw_number)]
    canonical = json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "ExecutionResult",
    "FeatureEngine",
    "FeatureDefinition",
]
