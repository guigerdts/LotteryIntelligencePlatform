"""Tests for opt/registry — core-4 optimizer registry (OE-09)."""

from __future__ import annotations

import pytest

from backend.app.opt.registry import (
    KNOWN_OPTIMIZERS,
    OPTIMIZER_SET_CORE_4,
    build_opt_registry,
    get_optimizer_defaults,
)


def test_optimizer_set_core4_identity() -> None:
    """OPTIMIZER_SET_CORE_4 is 'core-4' (OE-09)."""
    assert OPTIMIZER_SET_CORE_4 == "core-4"


def test_registry_returns_4_optimizers() -> None:
    """build_opt_registry() returns exactly 4 optimizers (OE-09)."""
    registry = build_opt_registry()
    assert len(registry) == 4
    assert set(registry.keys()) == {"ga", "pso", "bayesian", "sa"}


def test_registry_returns_fresh_params() -> None:
    """Each call to build_opt_registry() returns fresh param dicts."""
    r1 = build_opt_registry()
    r2 = build_opt_registry()
    assert r1 is not r2
    assert r1["ga"] is not r2["ga"]


def test_registry_params_are_dicts() -> None:
    """Every registry entry maps slug -> dict of params."""
    registry = build_opt_registry()
    for slug, params in registry.items():
        assert isinstance(params, dict), f"{slug} params must be a dict"


def test_known_optimizers_frozenset() -> None:
    """KNOWN_OPTIMIZERS is a frozenset of the 4 slugs."""
    assert isinstance(KNOWN_OPTIMIZERS, frozenset)
    assert KNOWN_OPTIMIZERS == {"ga", "pso", "bayesian", "sa"}


def test_get_optimizer_defaults_known() -> None:
    """get_optimizer_defaults() returns params for known optimizer."""
    params = get_optimizer_defaults("ga")
    assert isinstance(params, dict)
    assert "population_size" in params


def test_get_optimizer_defaults_unknown_raises() -> None:
    """get_optimizer_defaults() raises ValueError for unknown optimizer."""
    with pytest.raises(ValueError, match="Unknown optimizer"):
        get_optimizer_defaults("gradient_descent")
