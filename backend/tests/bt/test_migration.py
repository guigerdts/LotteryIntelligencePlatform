"""PR1 tests for Fase 10 BT: migration 0012 upgrade/downgrade.

These tests verify BTE-13:
- Migration 0012 creates bt_snapshots and bt_results tables
- Downgrade drops only bt_* tables
- No existing tables are modified
- Indexes are created correctly
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy import inspect

from alembic import command

# <repo>/backend/tests/bt -> <repo>/backend/tests -> <repo>/backend
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"

# The two bt-only tables added by 0012 (design Data Model, BTE-01).
BT_TABLES = {"bt_snapshots", "bt_results"}

# Alembic's own version-tracking table; not part of the domain schema.
_ALEMBIC_VERSION = "alembic_version"


def _domain_tables(db: Path) -> set[str]:
    """Return the schema table names (minus alembic's version table)."""
    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as conn:
            return {name for name in inspect(conn).get_table_names() if name != _ALEMBIC_VERSION}
    finally:
        engine.dispose()


def _migration_config(db: Path) -> Config:
    """Alembic Config pointed at a throwaway SQLite file."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    return cfg


class TestMigration0012:
    """Migration 0012 upgrade/downgrade (BTE-13)."""

    def test_upgrade_creates_bt_tables(self, tmp_path: Path) -> None:
        """Positive: upgrade creates bt_snapshots and bt_results."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)

        # Upgrade to head (includes 0012)
        command.upgrade(cfg, "head")

        tables = _domain_tables(db)
        assert "bt_snapshots" in tables
        assert "bt_results" in tables

    def test_downgrade_drops_only_bt_tables(self, tmp_path: Path) -> None:
        """BTE-13: downgrade drops only bt_* tables; other tables unchanged."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)

        # Upgrade to head
        command.upgrade(cfg, "head")

        # Verify bt_* exist
        tables_before = _domain_tables(db)
        assert "bt_snapshots" in tables_before
        assert "bt_results" in tables_before

        # Downgrade one step (0012 -> 0011)
        command.downgrade(cfg, "-1")

        tables_after = _domain_tables(db)
        assert "bt_snapshots" not in tables_after
        assert "bt_results" not in tables_after

        # Verify other tables still exist
        assert "lottery" in tables_after
        assert "draw" in tables_after
        assert "opt_snapshots" in tables_after

    def test_downgrade_only_drops_bt_objects(self, tmp_path: Path) -> None:
        """BTE-13: downgrade never touches core, stat_*, ml_*, dl_*, opt_*."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)

        # Upgrade to head
        command.upgrade(cfg, "head")

        tables_before = _domain_tables(db)

        # Downgrade one step
        command.downgrade(cfg, "-1")

        tables_after = _domain_tables(db)

        # All non-bt tables should be identical
        non_bt_before = tables_before - BT_TABLES
        non_bt_after = tables_after - BT_TABLES
        assert non_bt_before == non_bt_after

    def test_bt_snapshots_schema(self, tmp_path: Path) -> None:
        """Positive: bt_snapshots has correct columns."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)
        command.upgrade(cfg, "head")

        engine = sa.create_engine(f"sqlite:///{db}")
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                columns = {col["name"] for col in inspector.get_columns("bt_snapshots")}
                assert "id" in columns
                assert "lottery_id" in columns
                assert "strategy_id" in columns
                assert "fingerprint" in columns
                assert "version" in columns
                assert "status" in columns
                assert "config_json" in columns
                assert "created_at" in columns
        finally:
            engine.dispose()

    def test_bt_results_schema(self, tmp_path: Path) -> None:
        """Positive: bt_results has correct columns."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)
        command.upgrade(cfg, "head")

        engine = sa.create_engine(f"sqlite:///{db}")
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                columns = {col["name"] for col in inspector.get_columns("bt_results")}
                assert "id" in columns
                assert "snapshot_id" in columns
                assert "aggregate_metrics_json" in columns
                assert "window_history_json" in columns
                assert "created_at" in columns
        finally:
            engine.dispose()

    def test_bt_indexes_created(self, tmp_path: Path) -> None:
        """Positive: bt_* indexes are created."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)
        command.upgrade(cfg, "head")

        engine = sa.create_engine(f"sqlite:///{db}")
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                index_names = {idx["name"] for idx in inspector.get_indexes("bt_snapshots")}
                assert "ix_bt_snapshots_lottery_strategy" in index_names

                result_indexes = {idx["name"] for idx in inspector.get_indexes("bt_results")}
                assert "ix_bt_results_snapshot_id" in result_indexes
        finally:
            engine.dispose()

    def test_migration_idempotent_upgrade(self, tmp_path: Path) -> None:
        """Positive: upgrade can run twice without error."""
        db = tmp_path / "test.db"
        cfg = _migration_config(db)

        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")  # Should not error

        tables = _domain_tables(db)
        assert "bt_snapshots" in tables
        assert "bt_results" in tables
