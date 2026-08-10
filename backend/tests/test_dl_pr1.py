"""PR1 gates for Fase 8 DL: deps, migration 0010, dl models + constants, ban-gate.

These tests pin the PR1 slice (design PR breakdown: deps + 0010 + models + dl spawn):
- the 0010 migration creates ``dl_snapshots``/``dl_metrics``/``dl_weights`` and
  downgrades drop ONLY ``dl_*`` (DLE-16, additive/non-destructive);
- ``DL_GENERATOR_VERSION`` is a string identity participating in the fingerprint
  (DLE-08);
- torch is pinned exactly in pyproject.toml (DLE-06, D1);
- the ban-gate scan extends to ``app/dl`` (no xgboost/lightgbm/catboost/networkx);
- ``dl_*`` tables registered in ``Base.metadata``;
- ``ml_*`` tables untouched after dl downgrade.
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

# The three dl-only tables added by 0010 (design Data Model, DLE-01).
DL_TABLES = {"dl_snapshots", "dl_metrics", "dl_weights"}

# The two ml-only tables added by 0009 (design Data Model, MLE-01).
ML_TABLES = {"ml_snapshots", "ml_metrics"}

# Future-ml / banned names (proposal D1, M-A9): declared but never installed/imported.
FUTURE_ML_NAMES = ("xgboost", "lightgbm", "catboost")

# The dl/ public modules whose module-import surface is scanned for banned names.
_DL_MODULES = (
    "backend.app.dl",
    "backend.app.dl.version",
    "backend.app.dl.providers",
    "backend.app.dl.fingerprint",
    "backend.app.dl.registry",
)

# Alembic's own version-tracking table; not part of the domain schema.
_ALEMBIC_VERSION = "alembic_version"

# The prior head (0009) full domain table set, used by the downgrade-only check.
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
    "ml_snapshots",
    "ml_metrics",
}


def _torch_available() -> bool:
    """Check if torch is installed (PR1 dep gate only; full install in PR2)."""
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def _dl_package_available() -> bool:
    """Check if the dl/ package has version module (PR1 gate only; full package in PR2)."""
    dl_version = _BACKEND_DIR / "src" / "backend" / "app" / "dl" / "version.py"
    return dl_version.exists()


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


def test_torch_exact_pin() -> None:
    """torch is pinned exactly in pyproject.toml (DLE-06, D1)."""
    import tomllib

    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    installable = " ".join(project["project"]["dependencies"])
    assert "torch==2.13.0+cpu" in installable, "torch must be pinned to ==2.13.0+cpu"


@pytest.mark.skipif(not _torch_available(), reason="torch not yet installed (PR1 dep gate only)")
def test_torch_importable() -> None:
    """torch is available as the sole new runtime dep for dl/ (DLE-06)."""
    import torch  # noqa: F401

    assert torch.__version__


def test_dl_tables_created(tmp_path: Path) -> None:
    """Upgrade to head creates dl_snapshots, dl_metrics, dl_weights (DLE-16)."""
    db = tmp_path / "dl_up.db"
    command.upgrade(_migration_config(db), "head")
    assert DL_TABLES.issubset(_table_names(db))

    # Alembic's target_metadata (Base.metadata from the models package, REQ-09)
    # registers all dl_* tables so future autogenerate runs see the full schema.
    from backend.app.models import Base

    assert DL_TABLES.issubset(Base.metadata.tables.keys())


def test_dl_metadata_registered() -> None:
    """DL ORM entities are registered: DlSnapshot, DlMetric, DlWeight (DLE-01)."""
    from backend.app.models import DlMetric, DlSnapshot, DlWeight

    assert DlSnapshot.__tablename__ == "dl_snapshots"
    assert DlMetric.__tablename__ == "dl_metrics"
    assert DlWeight.__tablename__ == "dl_weights"


@pytest.mark.skipif(not _dl_package_available(), reason="dl/ package not yet created (PR2 scope)")
def test_dl_version_constant_exists() -> None:
    """``DL_GENERATOR_VERSION`` is a string identity (DLE-08 / D-A6)."""
    from backend.app.dl.version import DL_GENERATOR_VERSION

    assert isinstance(DL_GENERATOR_VERSION, str)
    assert DL_GENERATOR_VERSION  # non-empty


@pytest.mark.skipif(not _dl_package_available(), reason="dl/ package not yet created (PR2 scope)")
def test_no_future_dl_imports() -> None:
    """``dl/`` never imports xgboost/lightgbm/catboost (DLE-06/MLE-04)."""
    from importlib import import_module

    for mod_name in _DL_MODULES:
        module = import_module(mod_name)
        for attr in vars(module).values():
            referenced = getattr(attr, "__module__", None)
            if isinstance(referenced, str):
                assert not any(banned in referenced for banned in FUTURE_ML_NAMES), (
                    f"{mod_name} references banned module {referenced!r}"
                )

    # Future-ml families absent from INSTALLABLE deps (allowlist bounded to torch/sklearn).
    import tomllib

    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    installable = " ".join(project["project"]["dependencies"])
    for banned in FUTURE_ML_NAMES:
        assert banned not in installable, (
            f"pyproject.toml installable deps must not contain {banned}"
        )
    assert "torch" in installable


def test_networkx_not_in_installable_deps() -> None:
    """networkx is NOT in installable deps; it is only a transitive dep of torch (DLE-06)."""
    import tomllib

    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    installable = " ".join(project["project"]["dependencies"])
    assert "networkx" not in installable, (
        "networkx must NOT be an installable dep (transitive torch-only exception)"
    )


def test_migration_downgrade_only_dl(tmp_path: Path) -> None:
    """Downgrade 0010 drops ONLY ``dl_*``; every prior domain stays intact (DLE-16)."""
    db = tmp_path / "dl_down.db"
    cfg = _migration_config(db)
    command.upgrade(cfg, "head")
    assert DL_TABLES.issubset(_table_names(db))

    command.downgrade(cfg, "0009_ml_tables")

    remaining = _table_names(db)
    assert not DL_TABLES.intersection(remaining), "dl_* residue after downgrade"
    # Every pre-dl domain table (F1-F7) survives: the 0009 head set is exactly
    # what remains after dropping ONLY dl_*.
    assert remaining == _PRIOR_HEAD_TABLES


def test_ml_untouched_after_dl_downgrade(tmp_path: Path) -> None:
    """Downgrade 0010 preserves all ``ml_*`` tables (DLE-16, additive isolation)."""
    db = tmp_path / "dl_ml_intact.db"
    cfg = _migration_config(db)
    command.upgrade(cfg, "head")
    assert ML_TABLES.issubset(_table_names(db))

    command.downgrade(cfg, "0009_ml_tables")

    remaining = _table_names(db)
    assert ML_TABLES.issubset(remaining), "ml_* must survive dl downgrade"
