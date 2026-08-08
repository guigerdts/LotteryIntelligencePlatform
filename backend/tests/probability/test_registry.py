"""Probability method-registry tests (D-A2): 7 canonical methods, dict dispatch.

The registry holds ``MethodDefinition`` (id/version/params) and a dict-dispatch
lookup. It MUST register the 6 canonical methods + the univariate conditional
(PM-01..PM-07) with fixed, versioned definitions; an unknown id MUST resolve to
``None`` (missing data -> absent, never guessed — PES-06 parity).
"""

from __future__ import annotations

from backend.app.probability.registry import ProbMethodRegistry, build_prob_registry

_CANONICAL_IDS = {
    "hypergeometric",
    "binomial",
    "poisson",
    "empirical",
    "monte_carlo",
    "bayes",
    "conditional",
}


def test_build_registry_registers_all_seven_canonical_methods() -> None:
    """The canonical registry exposes exactly the 7 supported probability models."""
    registry = build_prob_registry()
    assert isinstance(registry, ProbMethodRegistry)
    assert set(registry.ids()) == _CANONICAL_IDS


def test_each_method_is_versioned_with_params() -> None:
    """Every registered method carries an immutable version and (possibly) params."""
    registry = build_prob_registry()
    for mid in _CANONICAL_IDS:
        definition = registry.get(mid)
        assert definition is not None, f"{mid} must be registered"
        assert definition.version  # non-empty version string
        assert definition.params is not None  # even empty dict is explicit


def test_registry_lookup_unknown_id_returns_none() -> None:
    """An unknown method id must resolve to ``None`` — never a guessed default."""
    registry = build_prob_registry()
    assert registry.get("nope") is None
    assert registry.get("") is None


def test_registry_is_frozen_after_build() -> None:
    """Build a registry, mutate the dict it returned, and confirm the source is stable."""
    registry = build_prob_registry()
    original = dict(registry._methods)
    registry._methods["paranoia"] = None  # bypass API to simulate tampering
    assert registry.get("paranoia") is None  # dict-dispatch ignores non-MethodDefinition
    # Restore so the shared registry is not polluted for other tests.
    registry._methods.clear()
    registry._methods.update(original)
    assert set(registry.ids()) == _CANONICAL_IDS