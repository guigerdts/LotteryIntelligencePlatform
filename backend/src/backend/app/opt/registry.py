"""Optimizer registry — dict-dispatch, core-4 scope (OE-09).

One source of truth for the four executed optimizers under
``optimizer_set="core-4"``: ``build_opt_registry()`` exposes canonical slugs
(``ga``, ``pso``, ``bayesian``, ``sa``). Unknown optimizers fail-fast listing
known IDs.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

# core-4 scope identity (OE-09): the ONLY executed optimizer set in Fase 9.
OPTIMIZER_SET_CORE_4: Final[str] = "core-4"

# Canonical core-4 definitions: (slug, default params). Insertion order IS the
# canonical training order; default params are JSON-serializable (they feed the
# fingerprint and ``opt_snapshots.algorithm_params``).
_CORE_4_SOURCE: Final[tuple[tuple[str, dict[str, object]], ...]] = (
    ("ga", {"population_size": 20, "generations": 50, "crossover_prob": 0.7, "mutation_prob": 0.2}),
    (
        "pso",
        {
            "swarm_size": 20,
            "max_iterations": 50,
            "inertia_weight": 0.7,
            "cognitive_coefficient": 1.5,
            "social_coefficient": 1.5,
        },
    ),
    ("bayesian", {"n_trials": 50, "sampler": "tpe"}),
    (
        "sa",
        {
            "max_iterations": 50,
            "initial_temperature": 1.0,
            "cooling_rate": 0.95,
            "perturbation_scale": 0.1,
        },
    ),
)


def build_opt_registry() -> Mapping[str, dict[str, object]]:
    """Build the executed core-4 registry keyed by canonical slug.

    Returns an immutable mapping slug -> default params. Every call returns
    fresh param dicts, so callers can never mutate the source table.
    """
    return MappingProxyType({slug: dict(params) for slug, params in _CORE_4_SOURCE})


# The set of known optimizer slugs (OE-09).
KNOWN_OPTIMIZERS: Final[frozenset[str]] = frozenset(slug for slug, _ in _CORE_4_SOURCE)


def get_optimizer_defaults(slug: str) -> dict[str, object]:
    """Return default params for a known optimizer, or raise ValueError."""
    if slug not in KNOWN_OPTIMIZERS:
        raise ValueError(
            f"Unknown optimizer {slug!r}. Known optimizers: {sorted(KNOWN_OPTIMIZERS)}"
        )
    return dict(_CORE_4_SOURCE[[s for s, _ in _CORE_4_SOURCE].index(slug)][1])


__all__ = [
    "OPTIMIZER_SET_CORE_4",
    "KNOWN_OPTIMIZERS",
    "build_opt_registry",
    "get_optimizer_defaults",
]
