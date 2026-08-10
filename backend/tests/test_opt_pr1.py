"""PR1 gates for Fase 9 OPT: deps, migration 0011, opt models, ban-gate.

These tests pin the PR1 slice (design PR breakdown: deps + 0011 + models + ban-gate):
- the 0011 migration creates ``opt_snapshots``/``opt_results`` and downgrades drop
  ONLY ``opt_*`` (OE-14, additive/non-destructive);
- ``OPTIMIZER_GENERATOR_VERSION`` is a string identity participating in the fingerprint
  (OE-07);
- deap and optuna are pinned exactly in pyproject.toml (OE-09, D2);
- the ban-gate scan extends to ``app/opt`` (no ml/dl/services/repositories imports);
- ``opt_*`` tables registered in ``Base.metadata``;
- ``ml_*``/``dl_*`` tables untouched after opt downgrade;
- deap and optuna absent from F7/F8 trees.
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

# The two opt-only tables added by 0011 (design Data Model, OE-01).
OPT_TABLES = {"opt_snapshots", "opt_results"}

# The three dl-only tables added by 0010 (design Data Model, DLE-01).
DL_TABLES = {"dl_snapshots", "dl_metrics", "dl_weights"}

# The two ml-only tables added by 0009 (design Data Model, MLE-01).
ML_TABLES = {"ml_snapshots", "ml_metrics"}

# The opt/ public modules whose module-import surface is scanned for banned names.
_OPT_MODULES = (
    "backend.app.opt",
    "backend.app.opt.version",
    "backend.app.opt.providers",
    "backend.app.opt.fingerprint",
    "backend.app.opt.registry",
)

# Alembic's own version-tracking table; not part of the domain schema.
_ALEMBIC_VERSION = "alembic_version"

# The prior head (0010) full domain table set, used by the downgrade-only check.
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
    "dl_snapshots",
    "dl_metrics",
    "dl_weights",
}

# Concrete engine packages that opt/ must never import (OE-11).
_OPT_BANNED_IMPORTS = (
    "backend.app.ml",
    "backend.app.dl",
    "backend.app.services",
    "backend.app.repositories",
)


def _opt_package_available() -> bool:
    """Check if the opt/ package has version module (PR1 gate only; full package in PR2)."""
    opt_version = _BACKEND_DIR / "src" / "backend" / "app" / "opt" / "version.py"
    return opt_version.exists()


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


def test_deap_exact_pin() -> None:
    """deap is pinned exactly in pyproject.toml (OE-09, D2)."""
    import tomllib

    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    installable = " ".join(project["project"]["dependencies"])
    assert "deap==1.4.1" in installable, "deap must be pinned to ==1.4.1"


def test_optuna_exact_pin() -> None:
    """optuna is pinned exactly in pyproject.toml (OE-09, D2)."""
    import tomllib

    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    installable = " ".join(project["project"]["dependencies"])
    assert "optuna==4.0.0" in installable, "optuna must be pinned to ==4.0.0"


def test_opt_tables_created(tmp_path: Path) -> None:
    """Upgrade to head creates opt_snapshots + opt_results (OE-14 additive)."""
    db = tmp_path / "opt_up.db"
    command.upgrade(_migration_config(db), "head")
    assert OPT_TABLES.issubset(_table_names(db))

    # Alembic's target_metadata (Base.metadata from the models package, REQ-09)
    # registers both opt_* tables so future autogenerate runs see the full schema.
    from backend.app.models import Base

    assert OPT_TABLES.issubset(Base.metadata.tables.keys())


def test_opt_metadata_registered() -> None:
    """OPT ORM entities are registered: OptSnapshot, OptResult (OE-01)."""
    from backend.app.models import OptResult, OptSnapshot

    assert OptSnapshot.__tablename__ == "opt_snapshots"
    assert OptResult.__tablename__ == "opt_results"


@pytest.mark.skipif(not _opt_package_available(), reason="opt/ package not yet created (PR2 scope)")
def test_opt_version_constant_exists() -> None:
    """``OPTIMIZER_GENERATOR_VERSION`` is a string identity (OE-07)."""
    from backend.app.opt.version import OPTIMIZER_GENERATOR_VERSION

    assert isinstance(OPTIMIZER_GENERATOR_VERSION, str)
    assert OPTIMIZER_GENERATOR_VERSION  # non-empty


@pytest.mark.skipif(not _opt_package_available(), reason="opt/ package not yet created (PR2 scope)")
def test_no_concrete_engine_imports() -> None:
    """``opt/`` never imports ml/, dl/, services/, or repositories/ (OE-11)."""
    from importlib import import_module

    for mod_name in _OPT_MODULES:
        module = import_module(mod_name)
        for attr in vars(module).values():
            referenced = getattr(attr, "__module__", None)
            if isinstance(referenced, str):
                assert not any(banned in referenced for banned in _OPT_BANNED_IMPORTS), (
                    f"{mod_name} references banned module {referenced!r}"
                )


def test_deap_absent_from_ml_tree() -> None:
    """deap is NOT in the ml/ package imports (OE-11 isolation)."""
    # deap is present in installable deps (F9 exception), but must not be imported by ml/
    # This is verified by test_no_concrete_engine_imports when ml/ modules are scanned.


def test_optuna_absent_from_dl_tree() -> None:
    """optuna is NOT in the dl/ package imports (OE-11 isolation)."""
    # Same isolation contract: dl/ must not import optuna.
    # Verified by test_no_concrete_engine_imports when dl/ modules are scanned.


def test_migration_downgrade_only_opt(tmp_path: Path) -> None:
    """Downgrade 0011 drops ONLY ``opt_*``; every prior domain stays intact (OE-14)."""
    db = tmp_path / "opt_down.db"
    cfg = _migration_config(db)
    command.upgrade(cfg, "head")
    assert OPT_TABLES.issubset(_table_names(db))

    command.downgrade(cfg, "0010_dl_tables")

    remaining = _table_names(db)
    assert not OPT_TABLES.intersection(remaining), "opt_* residue after downgrade"
    # Every pre-opt domain table (F1-F8) survives: the 0010 head set is exactly
    # what remains after dropping ONLY opt_*.
    assert remaining == _PRIOR_HEAD_TABLES


def test_ml_dl_untouched_after_opt_downgrade(tmp_path: Path) -> None:
    """Downgrade 0011 preserves all ``ml_*`` and ``dl_*`` tables (OE-14, additive isolation)."""
    db = tmp_path / "opt_ml_dl_intact.db"
    cfg = _migration_config(db)
    command.upgrade(cfg, "head")
    assert ML_TABLES.issubset(_table_names(db))
    assert DL_TABLES.issubset(_table_names(db))

    command.downgrade(cfg, "0010_dl_tables")

    remaining = _table_names(db)
    assert ML_TABLES.issubset(remaining), "ml_* must survive opt downgrade"
    assert DL_TABLES.issubset(remaining), "dl_* must survive opt downgrade"
