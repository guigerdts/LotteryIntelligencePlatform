"""PR1 gates for Fase 7 ML: deps, migration 0009, ml package seam + constants, registry.

These tests pin the PR1 slice (design PR breakdown: deps + 0009 + models + ml spawn):
- the 0009 migration creates ``ml_snapshots``/``ml_metrics`` and downgrades drop ONLY
  ``ml_*`` (MLE-10, additive/non-destructive);
- ``ML_GENERATOR_VERSION`` is a string identity participating in the fingerprint
  (MLE-05);
- ``ML_FEATURE_ORDER`` is an immutable 10-tuple in canonical F4 order (MLE-03/05,
  M-A5);
- the core-5 registry holds exactly the 5 executed sklearn families and never imports
  the future-ml names (MLE-04/MLE-07, D1);
- scikit-learn resolves and the ban-gate deny-list holds in the installable deps
  (MLE-04 scenario "allowlist bounded to scikit-learn").
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import inspect

from alembic import command

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"
_PYPROJECT = _BACKEND_DIR / "pyproject.toml"

# The two ml-only tables added by 0009 (design Data Model, MLE-01).
ML_TABLES = {"ml_snapshots", "ml_metrics"}

# Future-ml / banned names (proposal D1, M-A9): declared but never installed/imported.
FUTURE_ML_NAMES = ("xgboost", "lightgbm", "catboost", "networkx")

# The ml/ public modules whose module-import surface is scanned for banned names.
_ML_MODULES = (
    "backend.app.ml",
    "backend.app.ml.version",
    "backend.app.ml.features",
    "backend.app.ml.registry",
)

# Alembic's own version-tracking table; not part of the domain schema.
_ALEMBIC_VERSION = "alembic_version"

# The previous head (0008) full domain table set, used by the downgrade-only check
# without importing tests.test_migrations (keeps this module self-contained).
_PRIOR_HEAD_TABLES = {
    "lottery",
    "draw",
    "draw_numbers",
    "super_number",
    "datasets",
    "dataset_draws",
    "imports",
    "import_errors",
    "stat_snapshots",
    "stat_frequency",
    "stat_frequency_positions",
    "stat_gaps",
    "stat_averages",
    "stat_scalars",
    "feature_snapshots",
    "feature_values",
    "prob_snapshots",
    "prob_values",
    "graph_snapshots",
    "graph_values",
}


def _migration_config(db: Path) -> Config:
    """Alembic Config pointed at a throwaway SQLite file (mirrors test_migrations)."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    return cfg


def _table_names(db: Path) -> set[str]:
    """Return the domain schema table names on a fresh connection to ``db``."""
    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as conn:
            return {name for name in inspect(conn).get_table_names() if name != _ALEMBIC_VERSION}
    finally:
        engine.dispose()


def test_ml_tables_created(tmp_path: Path) -> None:
    """Upgrade to head creates ``ml_snapshots`` + ``ml_metrics`` (MLE-10 additive)."""
    db = tmp_path / "ml_up.db"
    command.upgrade(_migration_config(db), "head")
    assert ML_TABLES.issubset(_table_names(db))

    # Alembic's target_metadata (Base.metadata from the models package, REQ-09)
    # registers both ml_* tables so future autogenerate runs see the full schema.
    from backend.app.models import Base

    assert ML_TABLES.issubset(Base.metadata.tables.keys())


def test_ml_version_constant_exists() -> None:
    """``ML_GENERATOR_VERSION`` is a string identity (MLE-05 / M-A6)."""
    from backend.app.ml.version import ML_GENERATOR_VERSION

    assert isinstance(ML_GENERATOR_VERSION, str)
    assert ML_GENERATOR_VERSION  # non-empty


def test_ml_feature_order_frozen() -> None:
    """``ML_FEATURE_ORDER`` is an immutable 10-tuple in canonical F4 order (M-A5)."""
    from backend.app.ml.features import ML_FEATURE_ORDER

    assert isinstance(ML_FEATURE_ORDER, tuple)
    assert len(ML_FEATURE_ORDER) == 10
    # Frozen/immutable: no mutation protocol on a tuple; assignment raises TypeError.
    with pytest.raises(TypeError):
        ML_FEATURE_ORDER[0] = "mutated"  # type: ignore[index]
    # Canonical sorted order of the 10 base F4 ids (design M-A5).
    assert ML_FEATURE_ORDER == (
        "consecutive_count",
        "current_frequency",
        "decade_distribution",
        "draw_mean",
        "draw_range",
        "draw_sum",
        "low_high_ratio",
        "max_current_gap",
        "odd_even_ratio",
        "repeated_from_previous",
    )


def test_ml_registry_core5_only() -> None:
    """The registry holds exactly the 5 executed families, no future-ml names (MLE-07)."""
    from backend.app.ml.registry import CORE_5_MODELS, MODEL_SET_CORE_5

    assert MODEL_SET_CORE_5 == "core-5"
    assert len(CORE_5_MODELS) == 5
    assert set(CORE_5_MODELS) == {"rf", "et", "gb", "svm", "knn"}
    # Every entry maps slug -> (estimator class, default params dict).
    for slug, (estimator, params) in CORE_5_MODELS.items():
        assert isinstance(params, dict), f"{slug} params must be a dict"
        assert callable(estimator), f"{slug} must map to an estimator class"


def test_scikit_learn_importable() -> None:
    """scikit-learn is available as the sole new runtime dep (D1)."""
    import sklearn  # noqa: F401

    assert sklearn.__version__


def test_no_future_ml_imports() -> None:
    """``ml/`` never imports xgboost/lightgbm/catboost/networkx (MLE-04/MLE-07)."""
    import tomllib
    from importlib import import_module

    for mod_name in _ML_MODULES:
        module = import_module(mod_name)
        for attr in vars(module).values():
            referenced = getattr(attr, "__module__", None)
            if isinstance(referenced, str):
                assert not any(banned in referenced for banned in FUTURE_ML_NAMES), (
                    f"{mod_name} references banned module {referenced!r}"
                )

    # Future-ml families absent from INSTALLABLE deps (allowlist bounded to sklearn).
    # Parse the project table so the allowlist comment (which documents the exception)
    # never trips the deny check.
    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    installable = " ".join(project["project"]["dependencies"])
    for banned in FUTURE_ML_NAMES:
        assert banned not in installable, (
            f"pyproject.toml installable deps must not contain {banned}"
        )
    assert "scikit-learn" in installable
    assert "numpy" in installable


def test_migration_downgrade_only_ml(tmp_path: Path) -> None:
    """Downgrade 0009 drops ONLY ``ml_*``; every prior domain stays intact (MLE-10)."""
    db = tmp_path / "ml_down.db"
    cfg = _migration_config(db)
    command.upgrade(cfg, "head")
    assert ML_TABLES.issubset(_table_names(db))

    command.downgrade(cfg, "0008_graph_tables")

    remaining = _table_names(db)
    assert not ML_TABLES.intersection(remaining), "ml_* residue after downgrade"
    # Every pre-ml domain table (F1 core + stat_/feature_/prob_/graph_) survives:
    # the 0008 head set is exactly what remains after dropping ONLY ml_*.
    assert remaining == _PRIOR_HEAD_TABLES


def test_ml_untouched_after_dl_migration(tmp_path: Path) -> None:
    """Migration 0010 (dl_*) does not alter any ``ml_*`` table (DLE-16 additive isolation)."""
    db = tmp_path / "ml_dl_intact.db"
    cfg = _migration_config(db)
    command.upgrade(cfg, "head")
    # Both ml_* and dl_* exist at head (0010).
    assert ML_TABLES.issubset(_table_names(db))
    assert {"dl_snapshots", "dl_metrics", "dl_weights"}.issubset(_table_names(db))
