"""Generation weight construction (GEN-09): legitimate statistical levers only.

Builds the per-number sampling weights consumed by ``sampling.WeightedPool``.
The remix replaces the retired ``entry.score`` meta chain: a number's weight is
now a transparent function of draw history (F5 frequency × an optional cold
coverage boost), never a meta model score.
"""

from __future__ import annotations

from decimal import Decimal

COLD_BOOST: Decimal = Decimal("1.5")
"""Multiplier applied to COLD numbers to lift their sampling weight (PM-08)."""


def build_weights(
    probabilities: dict[int, float],
    coverage: dict[int, str],
    *,
    cold_boost: Decimal = COLD_BOOST,
) -> dict[int, float]:
    """Combine F5 probabilities with a cold-coverage boost into final weights.

    ``probabilities`` is the F5 number→probability map (probability engine).
    ``coverage`` maps each number to ``"cold"``/``"normal"``/``"hot"``; only
    ``"cold"`` numbers receive the ``cold_boost`` multiplier (lever C). The
    result preserves the key set of ``probabilities``.
    """
    boost = float(cold_boost)
    return {
        number: probability * (boost if coverage.get(number) == "cold" else 1.0)
        for number, probability in probabilities.items()
    }
