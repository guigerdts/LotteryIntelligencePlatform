"""Probability engine package (Fase 5 — Probability Engine).

Deterministic, result-only probability models (hypergeometric, binomial, Poisson,
empirical, Monte Carlo, Bayes, univariate conditional) that persist aggregates to
the dedicated ``prob_*`` schema. The engine depends ONLY on its own provider
Protocols (PES-06) and never writes outside ``prob_*`` (PES-01/02).
"""

from __future__ import annotations

# Probability Engine algorithm identity (PES-04/design D-05). Pinned independently
# of ``STATS_GENERATOR_VERSION``/``FEATURE_GENERATOR_VERSION``: a bump here never
# follows another engine's bump. Bump ONLY when an algorithm/params change alters
# persisted output; internal changes that leave output byte-identical do NOT bump.
PROB_GENERATOR_VERSION: str = "1.0.0"

__all__ = ["PROB_GENERATOR_VERSION"]