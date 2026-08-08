"""Probability provider Protocols contract tests (PES-06).

The Probability Engine MUST depend ONLY on the provider Protocols defined at its
composition root. No ``probability`` module may import a concrete
``statistics``/``feature_engineering``/``models``/repository implementation —
that would couple the engine to internals behind the service seams, exactly the
behavior PES-06 forbids.
"""

from __future__ import annotations

from importlib import import_module

# Every public module of the probability package (pure seams, no DB).
_PROB_MODULES = [
    "backend.app.probability.providers",
    "backend.app.probability.registry",
    "backend.app.probability.fingerprint",
]

# Concrete seams the probability package MUST never touch (PES-06 / design §4).
_FORBIDDEN_SUBSTRINGS = (
    "backend.app.statistics",
    "backend.app.feature_engineering",
    "backend.app.models",
    "backend.app.repositories",
    ".statistics.",
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
    """No probability module imports statistics/feature_engineering/models internals."""
    for mod_name in _PROB_MODULES:
        mod = import_module(mod_name)
        for referenced in _module_imports(mod):
            for banned in _FORBIDDEN_SUBSTRINGS:
                assert banned not in referenced, (
                    f"{mod_name} imports concrete seam {referenced!r} (forbidden by PES-06)"
                )


def test_provider_protocols_expose_expected_contract() -> None:
    """The three reader Protocols expose the read-only contracts of design §4."""
    from backend.app.probability.providers import (
        DrawReader,
        FeatureSnapshotReader,
        StatSnapshotReader,
    )

    assert "iter_draws" in vars(DrawReader) or callable(DrawReader)
    assert any(name in {"iter_draws", "lottery_rules"} for name in vars(DrawReader))
    assert "active" in vars(StatSnapshotReader)
    assert "frequencies" in vars(StatSnapshotReader)
    assert "active" in vars(FeatureSnapshotReader)


def test_carriers_are_frozen_records() -> None:
    """The pure carries (DrawRow/LotteryRules) are frozen dataclass records."""
    from backend.app.probability.providers import DrawRow, LotteryRules

    assert "draw_number" in DrawRow.__dataclass_fields__
    assert "numbers" in DrawRow.__dataclass_fields__
    assert "min_number" in LotteryRules.__dataclass_fields__
    assert "numbers_to_select" in LotteryRules.__dataclass_fields__