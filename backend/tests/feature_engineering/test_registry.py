"""FeatureRegistry: registration, Kahn topological order, cycle detection (FES-07).

Features declare explicit dependencies; the registry builds the directed graph and
runs Kahn topological sort. Any cycle fails-fast with the offending set and none of
the cycle members are registered. A feature whose dependency is
``future``/``disabled``/``failed`` is ``skipped``, never guessed (FES-07).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.app.feature_engineering.registry import (
    DISABLED,
    FAILED,
    FUTURE,
    FeatureCycleError,
    FeatureDefinition,
    FeatureRegistry,
)


def _def(
    feature_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    status: str = "active",
    source: str = "core",
) -> FeatureDefinition:
    return FeatureDefinition(
        id=feature_id,
        name=f"{feature_id} feature",
        category="core",
        description=f"{feature_id} computed feature",
        source=source,
        inputs=("draws",),
        algorithm=f"features/{feature_id}",
        params={},
        dependencies=dependencies,
        complexity="O(1)",
        version="1.0.0",
        status=status,
        history=(),
    )


def test_registry_emits_features_in_topological_order() -> None:
    """A base feature and a dependent feature run in dependency order."""
    registry = FeatureRegistry()
    registry.register(_def("base_1"))
    registry.register(_def("meta", dependencies=("base_1",)))
    assert registry.topological_order() == ["base_1", "meta"]


def test_registry_topo_order_respects_multiple_dependencies() -> None:
    """A feature depending on two features waits for both before running."""
    reg = FeatureRegistry()
    reg.register(_def("a"))
    reg.register(_def("b"))
    reg.register(_def("c", dependencies=("a", "b")))
    order = reg.topological_order()
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")


def test_registry_cycle_fails_fast_and_reports_offending_set() -> None:
    """Two features whose dependencies form a cycle raise and register nothing."""
    reg = FeatureRegistry()
    reg.register(_def("x", dependencies=("y",)))
    with pytest.raises(FeatureCycleError) as exc:
        reg.register(_def("y", dependencies=("x",)))
    assert "x" in exc.value.cycle
    assert "y" in exc.value.cycle


def test_registry_self_cycle_is_rejected() -> None:
    reg = FeatureRegistry()
    with pytest.raises(FeatureCycleError) as exc:
        reg.register(_def("self", dependencies=("self",)))
    assert "self" in exc.value.cycle


def test_registry_skips_disabled_dependency() -> None:
    """A feature depending on a disabled feature is skipped, never guessed."""
    reg = FeatureRegistry()
    reg.register(_def("disabled", status="disabled"))
    reg.register(_def("dep", dependencies=("disabled",)))
    assert reg.skipped() == {"dep"}
    assert "dep" not in reg.topological_order()


def test_registry_skips_future_dependency() -> None:
    reg = FeatureRegistry()
    reg.register(_def("future_statistics", status="future"))
    reg.register(_def("dep", dependencies=("future_statistics",)))
    assert reg.skipped() == {"dep"}
    assert "dep" not in reg.topological_order()


def test_registry_skips_failed_dependency() -> None:
    reg = FeatureRegistry()
    reg.register(_def("failed", status="failed"))
    reg.register(_def("dep", dependencies=("failed",)))
    assert reg.skipped() == {"dep"}
    assert "dep" not in reg.topological_order()


def test_registry_future_source_never_scheduled() -> None:
    """``source == 'future-statistics'`` is declared but never added to the run set."""
    reg = FeatureRegistry()
    reg.register(_def("correlation", source=FUTURE))
    assert reg.skipped() == {"correlation"}
    assert "correlation" not in reg.topological_order()


def test_status_constants_are_strings() -> None:
    assert DISABLED == "disabled"
    assert FAILED == "failed"
    assert FUTURE == "future"


def test_feature_definition_is_frozen() -> None:
    feat = _def("frozen_check")
    with pytest.raises(FrozenInstanceError):
        feat.params = {"x": 1}  # frozen dataclass forbids mutation
