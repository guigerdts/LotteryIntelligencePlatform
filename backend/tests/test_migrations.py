"""Migration lifecycle tests (REQ-09): alembic owns the schema, upgrade/downgrade round-trip.

The tests drive alembic programmatically against a tmp SQLite file so the real
``database/lip.db`` is never touched. They assert the two-revision contract:
0001 owns integrity only (PK/FK/UNIQUE/CHECK and constraint-implied indexes, NO
explicit performance indexes) and 0002 adds exactly the four pre-approved
performance indexes, additively and reversibly (PR-5). Note: SQLAlchemy's
SQLite inspector reports explicit ``CREATE INDEX`` indexes via ``get_indexes``
while UNIQUE-constraint auto-indexes surface via ``get_unique_constraints``.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import inspect

from alembic import command

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

EXPECTED_TABLES = {
    "lottery",
    "draw",
    "draw_numbers",
    "super_number",
    "datasets",
    "dataset_draws",
}

# Alembic's own version-tracking table; not part of the domain schema.
_ALEMBIC_VERSION = "alembic_version"


def _domain_tables(db: Path) -> set[str]:
    """Return the schema table names (minus alembic's version table) via a fresh connection."""
    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as conn:
            return {name for name in inspect(conn).get_table_names() if name != _ALEMBIC_VERSION}
    finally:
        engine.dispose()


EXPECTED_UNIQUE = {
    "lottery": {"uq_lottery_code"},
    "draw": {"uq_draw_lottery_draw_number"},
    "draw_numbers": {"uq_draw_numbers_draw_position", "uq_draw_numbers_draw_number"},
    "super_number": {"uq_super_number_draw_id"},
    "datasets": {"uq_datasets_version"},
    "dataset_draws": {"uq_dataset_draws_pair"},
}

EXPECTED_CHECKS = {
    "lottery": {"ck_lottery_min_max", "ck_lottery_numbers_to_select", "ck_lottery_super_range"}
}

# Revision identifiers used to pin the 0001-only vs head (0002) states.
_REV_0001 = "0001_initial_core_domain"

# The four performance indexes shipped by 0002 (design Indexes table, Performance).
PERFORMANCE_INDEXES = {
    "ix_draw_lottery_date": ("draw", ("lottery_id", "draw_date")),
    "ix_draw_lottery_id": ("draw", ("lottery_id",)),
    "ix_draw_numbers_draw_id": ("draw_numbers", ("draw_id",)),
    "ix_dataset_draws_draw_id": ("dataset_draws", ("draw_id",)),
}


def _config(db_path: Path) -> Config:
    """Build an alembic Config pointed at the throwaway SQLite file."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_zero_tables_before_upgrade(tmp_path: Path) -> None:
    """A freshly created DB file (as init_db makes it) has zero tables (REQ-05/REQ-09)."""
    db = tmp_path / "empty.db"
    db.touch()  # simulate init_db file creation (no schema)
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        tables = inspect(conn).get_table_names()
    engine.dispose()
    assert tables == []


def test_upgrade_0001_creates_tables_constraints_no_perf_indexes(tmp_path: Path) -> None:
    """0001 creates the 6 tables with UNIQUE/FK/CHECK and NO explicit perf indexes."""
    db = tmp_path / "up.db"
    command.upgrade(_config(db), _REV_0001)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert _domain_tables(db) == EXPECTED_TABLES

        # UNIQUE constraints match the model contract (constraint-implied indexes).
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names), f"{table} missing UNIQUE {expected - names}"

        # CHECK constraints on lottery.
        check_names = {ck["name"] for ck in insp.get_check_constraints("lottery")}
        assert EXPECTED_CHECKS["lottery"].issubset(check_names), (
            f"lottery missing CHECK {EXPECTED_CHECKS['lottery'] - check_names}"
        )

        # FK RESTRICT via inspector.
        fk_specs = {t: {f["name"] for f in insp.get_foreign_keys(t)} for t in EXPECTED_TABLES}
        assert fk_specs["draw"], "draw should declare an FK to lottery"
        assert fk_specs["dataset_draws"], "dataset_draws should declare FKs"

        # 0001 must NOT create explicit performance indexes: get_indexes() reports
        # only explicit CREATE INDEX ops on SQLite, and every explicit index on a
        # 0001-only schema must be absent — the (lottery_id, draw_date) index is
        # deferred to 0002 (PR-5).
        for table in EXPECTED_TABLES:
            assert insp.get_indexes(table) == [], f"{table} leaked an explicit index at 0001"
    finally:
        engine.dispose()


def test_upgrade_head_0002_adds_performance_indexes(tmp_path: Path) -> None:
    """head (0002) adds exactly the four pre-approved performance indexes."""
    db = tmp_path / "head.db"
    command.upgrade(_config(db), "head")

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert _domain_tables(db) == EXPECTED_TABLES

        # Integrity contract survives: every UNIQUE constraint from 0001 is intact.
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names), f"{table} missing UNIQUE {expected - names}"

        # The four performance indexes exist with the correct columns.
        for name, (table, columns) in PERFORMANCE_INDEXES.items():
            idx = {i["name"]: i for i in insp.get_indexes(table)}
            assert name in idx, f"missing index {name} on {table}"
            assert tuple(idx[name]["column_names"]) == columns
            assert not idx[name]["unique"]  # performance, not integrity

        # Each explicit index is a real CREATE INDEX (sql IS NOT NULL in
        # sqlite_master), not an auto-index from a UNIQUE constraint.
        with engine.connect() as conn:
            master = {
                row[0]: row[1]
                for row in conn.exec_driver_sql(
                    "SELECT name, sql FROM sqlite_master WHERE type='index'"
                ).all()
            }
        for name in PERFORMANCE_INDEXES:
            assert master.get(name) is not None, f"{name} missing from sqlite_master"
    finally:
        engine.dispose()


def test_downgrade_0002_removes_only_performance_indexes(tmp_path: Path) -> None:
    """Downgrade to 0001 drops the four perf indexes; tables + integrity survive."""
    db = tmp_path / "cycle.db"
    cfg = _config(db)
    command.upgrade(cfg, "head")

    command.downgrade(cfg, _REV_0001)
    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        # All six domain tables remain.
        assert _domain_tables(db) == EXPECTED_TABLES
        # No explicit performance index remains on any table.
        for table in EXPECTED_TABLES:
            explicit = insp.get_indexes(table)
            assert explicit == [], f"{table} still has an explicit index at 0001"
        # Integrity constraints survive.
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names)
    finally:
        engine.dispose()


def test_downgrade_base_drops_all_then_reupgrade_succeeds(tmp_path: Path) -> None:
    """Downgrade to base drops every table; a subsequent upgrade recreates them (G3/G4)."""
    db = tmp_path / "cycle.db"
    cfg = _config(db)

    command.upgrade(cfg, "head")
    assert _domain_tables(db) == EXPECTED_TABLES

    command.downgrade(cfg, "base")
    # Alembic keeps its version table; every domain table must be dropped.
    assert _domain_tables(db) == set()

    command.upgrade(cfg, "head")
    assert _domain_tables(db) == EXPECTED_TABLES
