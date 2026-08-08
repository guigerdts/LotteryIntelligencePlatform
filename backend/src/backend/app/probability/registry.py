"""Probability method registry — dict-dispatch, no Kahn dependency (D-A2).

Registers the 7 canonical model definitions (PM-01..PM-07) as immutable
:class:`MethodDefinition` records with id/name/description/params/version.
Lookup is a plain dict dispatch (the probability models are independent — the
F4 Kahn DAG has no role here, D-A2); an unknown id returns ``None`` and is never
guessed (PES-06 parity). ``PROB_GENERATOR_VERSION`` is pinned independently of
``STATS_``/``FEATURE_`` versions (PES-04).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.app.probability import PROB_GENERATOR_VERSION


@dataclass(frozen=True)
class MethodDefinition:
    """Immutable declaration of one probability model (PM-01..PM-07)."""

    id: str
    name: str
    description: str
    params: Mapping[str, object] = field(default_factory=dict)
    version: str = PROB_GENERATOR_VERSION


class ProbMethodRegistry:
    """Holds the registered method definitions and a dict-dispatch lookup.

    ``register`` inserts a frozen definition; ``get`` returns it or ``None`` for
    an unknown id (never a guessed default). ``ids`` enumerates in insertion
    order; ``definitions`` exposes the raw mapping read-only.
    """

    def __init__(self) -> None:
        self._methods: dict[str, MethodDefinition] = {}

    def register(self, definition: MethodDefinition) -> None:
        self._methods[definition.id] = definition

    def get(self, method_id: str) -> MethodDefinition | None:
        return self._methods.get(method_id)

    def ids(self) -> list[str]:
        return list(self._methods)

    def definitions(self) -> Mapping[str, MethodDefinition]:
        return self._methods


def build_prob_registry() -> ProbMethodRegistry:
    """Return the canonical registry: all 7 probability models registered.

    Each model carries its frozen, immutable params under the shared
    ``PROB_GENERATOR_VERSION`` (PES-04). ``monte_carlo`` declares the default
    ``n_simulations`` that participates in the seed (PES-05).
    """
    registry = ProbMethodRegistry()
    registry.register(
        MethodDefinition(
            id="hypergeometric",
            name="Hypergeometric",
            description="Exact hypergeometric P(X=k)=C(r,k)C(N-r,n-k)/C(N,n) over the lottery pool",
            params={"N": None, "n": None, "r": None},
        )
    )
    registry.register(
        MethodDefinition(
            id="binomial",
            name="Binomial",
            description="Exact binomial P(X=k)=C(n,k) p^k (1-p)^(n-k)",
            params={"n": None, "p": None},
        )
    )
    registry.register(
        MethodDefinition(
            id="poisson",
            name="Poisson",
            description="Poisson P(X=k)=lambda^k e^-lambda / k! at fixed Decimal precision",
            params={"lambda": None, "kmax": None},
        )
    )
    registry.register(
        MethodDefinition(
            id="empirical",
            name="Empirical",
            description=(
                "Empirical P(subject)=count(subject)/total from the stat frequency snapshot"
            ),
            params={"total": None},
        )
    )
    registry.register(
        MethodDefinition(
            id="monte_carlo",
            name="Monte Carlo",
            description=(
                "Fixed-seed Monte Carlo simulation; per-subject aggregates + "
                "p50/p90/p99 quantiles"
            ),
            params={"n_simulations": 10_000, "pool": None, "n_select": None},
        )
    )
    registry.register(
        MethodDefinition(
            id="bayes",
            name="Bayesian Posterior",
            description=(
                "Empirical-Bayes posterior fold: posterior ~ prior x likelihood over frozen data"
            ),
            params={"prior": "uniform"},
        )
    )
    registry.register(
        MethodDefinition(
            id="conditional",
            name="Univariate Conditional",
            description=(
                "P(subject | window) = count_in_window / window_size; univariate "
                "only, never joint/pairwise"
            ),
            params={"window_size": None},
        )
    )
    return registry


__all__ = ["MethodDefinition", "ProbMethodRegistry", "build_prob_registry"]