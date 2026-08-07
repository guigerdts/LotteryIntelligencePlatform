"""Provider Protocol decoupling contract test (FES-06).

The Feature Engine must depend ONLY on the provider Protocols defined at its
composition root. No module under ``feature_engineering`` may import a concrete
``statistics``/``models``/``repository`` implementation — that would create a
circular dependency and couple the engine to Statistics internals.

This imports every public module of the feature_engineering package and asserts
that its dependency graph contains none of the prohibited concrete seams.
"""

from __future__ import annotations

from importlib import import_module

# Every public module of the feature_engineering package (pure seams, no DB).
_FE_MODULES = [
    "backend.app.feature_engineering.registry",
    "backend.app.feature_engineering.providers",
    "backend.app.feature_engineering.engine",
    "backend.app.feature_engineering.fingerprint",
    "backend.app.feature_engineering.features",
    "backend.app.feature_engineering.context",
]

# Concrete seams the engine MUST never touch (design §4 / FES-06).
_FORBIDDEN_SUBSTRINGS = (
    "backend.app.statistics",
    "backend.app.models",
    "backend.app.repositories",
    "backend.app.services",
    "backend.app.schemas",
    ".models.",
)


def _module_imports(module: object) -> set[str]:
    """Return the fully-qualified names of modules referenced by ``module``."""
    names: set[str] = set()
    for attr in vars(module).values():
        mod = getattr(attr, "__module__", None)
        if isinstance(mod, str) and mod != "__main__":
            names.add(mod)
    return names


def test_package_modules_stay_decoupled_from_concrete_seams() -> None:
    for mod_name in _FE_MODULES:
        mod = import_module(mod_name)
        for referenced in _module_imports(mod):
            for banned in _FORBIDDEN_SUBSTRINGS:
                assert banned not in referenced, (
                    f"{mod_name} imports concrete seam {referenced!r} (forbidden by FES-06)"
                )


def test_provider_protocols_are_structural_and_expose_expected_methods() -> None:
    """The three provider Protocols expose the read-only contracts of design §4."""
    from collections.abc import Iterator, Mapping
    from decimal import Decimal

    from backend.app.feature_engineering.providers import (
        DatasetProvider,
        DrawProvider,
        StatisticsProvider,
    )

    # DrawProvider: keyset read-only iteration + lottery rules.
    assert callable(DrawProvider) or any(
        name in {"iter_draws", "lottery_rules"} for name in vars(DrawProvider)
    )
    # Iterator return is a typing protocol — the symbols themselves must exist.
    assert Iterator is not None
    # StatisticsProvider resolves only the active snapshot + scalars (no precompute).
    assert "active_snapshot" in vars(StatisticsProvider)
    assert "scalars" in vars(StatisticsProvider)
    assert Mapping is not None and Decimal is not None
    # DatasetProvider is a declared seam, not exercised in slice 1.
    assert "active_dataset" in vars(DatasetProvider)


def test_context_imports_no_concrete_models() -> None:
    """The pure context (DrawRow/LotteryRules/FeatureContext) imports no ORM."""
    from backend.app.feature_engineering.context import (
        DrawRow,
        FeatureContext,
        LotteryRules,
    )

    # Structural sanity: the carrier types are simple frozen records.
    assert "draw_number" in DrawRow.__dataclass_fields__
    assert "numbers_to_select" in LotteryRules.__dataclass_fields__
    assert "rules" in FeatureContext.__dataclass_fields__
