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

# F1's six core-domain tables (the 0001 schema).
EXPECTED_TABLES = {
    "lottery",
    "draw",
    "draw_numbers",
    "super_number",
    "datasets",
    "dataset_draws",
}

# The two import-engine audit tables added by 0003 (design §4).
IMPORT_TABLES = {"imports", "import_errors"}

# The six statistics tables added by 0005 (design §2) — independent stat_* domain.
STAT_TABLES = {
    "stat_snapshots",
    "stat_frequency",
    "stat_frequency_positions",
    "stat_gaps",
    "stat_averages",
    "stat_scalars",
}

# The two feature-engine tables added by 0006 (design §2) — independent feature_* domain.
FEATURE_TABLES = {"feature_snapshots", "feature_values"}

# The two probability-engine tables added by 0007 (design Data Model) — prob_* domain.
PROB_TABLES = {"prob_snapshots", "prob_values"}

# The full schema at head (0007) = F1 tables + import tables + stat_* + feature_* + prob_*.
HEAD_TABLES = EXPECTED_TABLES | IMPORT_TABLES | STAT_TABLES | FEATURE_TABLES | PROB_TABLES

# The schema reached at 0006 (before the prob_* domain).
FEATURE_HEAD_TABLES = HEAD_TABLES - PROB_TABLES

# The schema reached at 0005 (before the feature_* domain).
STAT_HEAD_TABLES = HEAD_TABLES - FEATURE_TABLES - PROB_TABLES

# The schema reached at 0003 (before the 0005 stat_* domain).
IMPORT_HEAD_TABLES = EXPECTED_TABLES | IMPORT_TABLES

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

# The four F1 performance indexes shipped by 0002 (design Indexes table, Performance).
PERFORMANCE_INDEXES = {
    "ix_draw_lottery_date": ("draw", ("lottery_id", "draw_date")),
    "ix_draw_lottery_id": ("draw", ("lottery_id",)),
    "ix_draw_numbers_draw_id": ("draw_numbers", ("draw_id",)),
    "ix_dataset_draws_draw_id": ("dataset_draws", ("draw_id",)),
}

# The import-engine performance indexes shipped by 0004 (design §4, Performance row).
IMPORT_PERF_INDEXES = {
    "ix_imports_lottery_status_started": ("imports", ("lottery_id", "status", "started_at")),
    "ix_imports_checksum": ("imports", ("checksum",)),
    "ix_import_errors_import_id": ("import_errors", ("import_id",)),
}

# Revision identifiers used to pin migration states.
_REV_0003 = "0003_imports_audit"
_REV_0004 = "0004_import_performance_indexes"
_REV_0005 = "0005_stat_tables"
_REV_0006 = "0006_feature_tables"
_REV_0007 = "0007_probability_tables"


# The statistics (0005) indexes (design §4, Indexes table: stat_* only).
STAT_INDEXES = {
    "ix_snap_lottery_metric_status": ("stat_snapshots", ("lottery_id", "metric_set", "status")),
    "ix_stat_frequency_snapshot_id": ("stat_frequency", ("snapshot_id",)),
    "ix_stat_frequency_positions_snapshot_id": ("stat_frequency_positions", ("snapshot_id",)),
    "ix_stat_gaps_snapshot_id": ("stat_gaps", ("snapshot_id",)),
    "ix_stat_averages_snapshot_id": ("stat_averages", ("snapshot_id",)),
    "ix_stat_scalars_snapshot_id": ("stat_scalars", ("snapshot_id",)),
}

# 0005 expectation: the stat_* tables present at head have their integrity
# constraints (UNIQUE/CHECK) and the full import + core set remains intact.
STAT_SNAPSHOT_CHECKS = {"ck_stat_snapshots_range", "ck_stat_snapshots_status"}
STAT_SNAPSHOT_UNIQUE = {"uq_stat_snapshots_scope_version"}

# The feature-engine indexes shipped by 0006 (design §3, Feature tables).
FEATURE_INDEXES = {
    "ix_fsnap_lottery_set_status": (
        "feature_snapshots",
        ("lottery_id", "feature_set", "status"),
    ),
    "ix_fval_snapshot_id": ("feature_values", ("snapshot_id",)),
    "ix_fval_feature_draw": ("feature_values", ("feature_id", "draw_number")),
}

# 0006 expectations: feature_snapshots integrity + FK RESTRICT to lottery.
FEATURE_SNAPSHOT_CHECKS = {"ck_feature_snapshots_range", "ck_feature_snapshots_status"}
FEATURE_SNAPSHOT_UNIQUE = {"uq_feature_snapshots_scope_version"}

# The probability-engine indexes shipped by 0007 (design Migration, PES-09 names).
PROB_INDEXES = {
    "ix_psnap_lottery_model_status": (
        "prob_snapshots",
        ("lottery_id", "model_set", "status"),
    ),
    "ix_pval_snapshot_id": ("prob_values", ("snapshot_id",)),
    "ix_pval_subject": ("prob_values", ("subject",)),
}

# 0007 expectations: prob_snapshots integrity + FK RESTRICT to lottery.
PROB_SNAPSHOT_CHECKS = {"ck_prob_snapshots_range", "ck_prob_snapshots_status"}
PROB_SNAPSHOT_UNIQUE = {"uq_prob_snapshots_scope_version"}


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


def test_upgrade_head_0004_adds_f1_and_import_performance_indexes(tmp_path: Path) -> None:
    """head (0004) adds the four F1 perf indexes PLUS the three import perf indexes."""
    db = tmp_path / "head.db"
    command.upgrade(_config(db), "head")

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert _domain_tables(db) == HEAD_TABLES

        # Integrity contract survives: every UNIQUE constraint from 0001 is intact.
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names), f"{table} missing UNIQUE {expected - names}"

        # The import tables must exist with their CHECK/FK constraints (0003).
        assert {"imports", "import_errors"}.issubset(HEAD_TABLES)
        check_names = {ck["name"] for ck in insp.get_check_constraints("imports")}
        assert "ck_imports_status" in check_names
        assert "ck_imports_import_type" in check_names

        # All performance indexes (F1 + import) exist with the correct columns.
        for name, (table, columns) in {**PERFORMANCE_INDEXES, **IMPORT_PERF_INDEXES}.items():
            idx = {i["name"]: i for i in insp.get_indexes(table)}
            assert name in idx, f"missing index {name} on {table}"
            assert tuple(idx[name]["column_names"]) == columns
            assert not idx[name]["unique"]  # performance, not integrity

        # Each explicit index is a real CREATE INDEX (sql IS NOT NULL in sqlite_master).
        with engine.connect() as conn:
            master = {
                row[0]: row[1]
                for row in conn.exec_driver_sql(
                    "SELECT name, sql FROM sqlite_master WHERE type='index'"
                ).all()
            }
        for name in {**PERFORMANCE_INDEXES, **IMPORT_PERF_INDEXES}:
            assert master.get(name) is not None, f"{name} missing from sqlite_master"
    finally:
        engine.dispose()


def test_upgrade_0003_creates_import_tables_with_integrity_no_import_perf_indexes(
    tmp_path: Path,
) -> None:
    """0003 alone creates imports/import_errors with CHECK/FK and NO import perf indexes."""
    db = tmp_path / "up_import.db"
    command.upgrade(_config(db), _REV_0003)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert (
            _domain_tables(db) == IMPORT_HEAD_TABLES
        )  # 0004 only adds perf indexes -> still present

        # Integrity: PK, CHECK on imports status/import_type and per-counter >= 0.
        check_names = {ck["name"] for ck in insp.get_check_constraints("imports")}
        assert {"ck_imports_status", "ck_imports_import_type"}.issubset(check_names)
        assert any(name.endswith("_non_negative") for name in check_names)

        # FK RESTRICT declared on both import tables.
        imports_fk = {f["name"] or "anonymous" for f in insp.get_foreign_keys("imports")}
        errors_fk = {f["name"] or "anonymous" for f in insp.get_foreign_keys("import_errors")}
        assert imports_fk and errors_fk

        # No explicit performance index yet (0004 not applied).
        assert insp.get_indexes("imports") == []
        assert insp.get_indexes("import_errors") == []
    finally:
        engine.dispose()


def test_downgrade_0002_removes_only_performance_indexes(tmp_path: Path) -> None:
    """Downgrade to 0001 drops the F1 perf indexes AND the import tables; integrity survives."""
    db = tmp_path / "cycle.db"
    cfg = _config(db)
    command.upgrade(cfg, "head")

    command.downgrade(cfg, _REV_0001)
    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        # All six domain tables remain (import tables 0003 were also dropped).
        assert _domain_tables(db) == EXPECTED_TABLES
        # No explicit performance index remains on any table.
        for table in EXPECTED_TABLES:
            explicit = insp.get_indexes(table)
            assert explicit == [], f"{table} still has an explicit index at {_REV_0001}"
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
    assert _domain_tables(db) == HEAD_TABLES

    command.downgrade(cfg, "base")
    # Alembic keeps its version table; every domain table must be dropped.
    assert _domain_tables(db) == set()

    command.upgrade(cfg, "head")
    assert _domain_tables(db) == HEAD_TABLES


def test_upgrade_0005_creates_stat_tables_with_integrity_and_indexes(tmp_path: Path) -> None:
    """0005 adds the six stat_* tables (integrity + indexes); core/import untouched."""
    db = tmp_path / "up_stat.db"
    cfg = _config(db)
    command.upgrade(cfg, _REV_0005)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert _domain_tables(db) == STAT_HEAD_TABLES

        # stat_snapshots integrity: UNIQUE(lottery_id, metric_set, version) and
        # CHECK(range/status) constraints, plus FK RESTRICT to lottery.
        unique = {uc["name"] for uc in insp.get_unique_constraints("stat_snapshots")}
        assert STAT_SNAPSHOT_UNIQUE.issubset(unique)
        checks = {ck["name"] for ck in insp.get_check_constraints("stat_snapshots")}
        assert STAT_SNAPSHOT_CHECKS.issubset(checks)
        fk_lottery = {
            fk["constrained_columns"][0] for fk in insp.get_foreign_keys("stat_snapshots")
        }
        assert "lottery_id" in fk_lottery

        # Every payload table has a composite PK (snapshot_id first) and FK to the header.
        for table in STAT_TABLES - {"stat_snapshots"}:
            pk = set(insp.get_pk_constraint(table)["constrained_columns"])
            assert "snapshot_id" in pk, f"{table} missing snapshot_id in PK"
            fk_cols = {
                col for fk in insp.get_foreign_keys(table) for col in fk["constrained_columns"]
            }
            assert fk_cols == {"snapshot_id"}, f"{table} missing FK to stat_snapshots"

        # All stat_* indexes exist with the correct columns (design §4).
        for name, (table, columns) in STAT_INDEXES.items():
            idx = {i["name"]: i for i in insp.get_indexes(table)}
            assert name in idx, f"missing index {name} on {table}"
            assert tuple(idx[name]["column_names"]) == columns
            assert not idx[name]["unique"]  # performance, not integrity

        # The status CHECK must accept 'failed' (design §3 batch-fail policy).
        # Insert a parent lottery first so the FK RESTRICT does not block the
        # snapshot row regardless of the SQLite FK pragma default.
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO lottery (id, code, name, country, min_number, max_number,"
                " numbers_to_select, super_number_min, super_number_max,"
                " created_at)"
                " VALUES (1, 'L1', 'Lottery 1', 'AR', 1, 45, 5, NULL, NULL,"
                "  '2026-08-07T00:00:00Z')"
            )
            conn.exec_driver_sql(
                "INSERT INTO stat_snapshots"
                " (id, lottery_id, metric_set, version, generator_version, engine_version,"
                "  checksum, status, is_locked, draw_count, draws_from, draws_to,"
                "  created_at, updated_at)"
                " VALUES (1, 1, 'core', '1', '1.0.0', '1',"
                "  'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',"
                "  'failed', 0, 0, 0, 0,"
                "  '2026-08-07T00:00:00Z', '2026-08-07T00:00:00Z')"
            )

        # Core-domain tables keep their UNIQUE integrity (Option A: no core change).
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names), f"{table} missing UNIQUE {expected - names}"
    finally:
        engine.dispose()


def test_downgrade_0005_drops_only_stat_tables_core_untouched(tmp_path: Path) -> None:
    """Downgrade from head to 0004 removes ONLY stat_*; core/import tables survive."""
    db = tmp_path / "down_stat.db"
    cfg = _config(db)
    command.upgrade(cfg, "head")
    assert _domain_tables(db) == HEAD_TABLES

    command.downgrade(cfg, _REV_0004)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        # Exactly the F1 + import tables remain — no stat_* residue, no core loss.
        assert _domain_tables(db) == IMPORT_HEAD_TABLES
        # No stat_* index leaks.
        for name, (table, _columns) in STAT_INDEXES.items():
            if table in _domain_tables(db):
                idx = {i["name"] for i in insp.get_indexes(table)}
                assert name not in idx, f"{name} leaked after downgrade"
    finally:
        engine.dispose()


def test_upgrade_0006_creates_feature_tables_with_integrity_and_indexes(
    tmp_path: Path,
) -> None:
    """0006 adds the two feature_* tables (integrity + indexes); core/stat_* untouched."""
    db = tmp_path / "up_feature.db"
    cfg = _config(db)
    command.upgrade(cfg, _REV_0006)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert _domain_tables(db) == FEATURE_HEAD_TABLES

        # feature_snapshots integrity: UNIQUE(...), CHECK(range/status), FK RESTRICT.
        unique = {uc["name"] for uc in insp.get_unique_constraints("feature_snapshots")}
        assert FEATURE_SNAPSHOT_UNIQUE.issubset(unique)
        checks = {ck["name"] for ck in insp.get_check_constraints("feature_snapshots")}
        assert FEATURE_SNAPSHOT_CHECKS.issubset(checks)
        fk_lottery = {
            fk["constrained_columns"][0] for fk in insp.get_foreign_keys("feature_snapshots")
        }
        assert "lottery_id" in fk_lottery

        # feature_values: composite PK (snapshot_id first) + FK to the header, no FK to draw.
        pk = set(insp.get_pk_constraint("feature_values")["constrained_columns"])
        assert "snapshot_id" in pk
        assert "feature_id" in pk
        assert "draw_number" in pk
        fk_cols = {
            col
            for fk in insp.get_foreign_keys("feature_values")
            for col in fk["constrained_columns"]
        }
        assert fk_cols == {"snapshot_id"}

        # All feature_* indexes exist with the correct columns (design §3).
        for name, (table, columns) in FEATURE_INDEXES.items():
            idx = {i["name"]: i for i in insp.get_indexes(table)}
            assert name in idx, f"missing index {name} on {table}"
            assert tuple(idx[name]["column_names"]) == columns
            assert not idx[name]["unique"]  # performance, not integrity

        # The excepted status CHECK accepts 'failed' (design §7 fail policy).
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO lottery (id, code, name, country, min_number, max_number,"
                " numbers_to_select, super_number_min, super_number_max, created_at)"
                " VALUES (1, 'L1', 'Lottery 1', 'AR', 1, 45, 5, NULL, NULL,"
                "  '2026-08-07T00:00:00Z')"
            )
            conn.exec_driver_sql(
                "INSERT INTO feature_snapshots"
                " (id, lottery_id, feature_set, version, feature_engine_version, checksum,"
                "  input_fingerprint, status, is_locked, draw_count, draws_from, draws_to,"
                "  created_at, updated_at)"
                " VALUES (1, 1, 'core', '1', '1.0.0',"
                "  'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',"
                "  'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',"
                "  'failed', 0, 0, 0, 0,"
                "  '2026-08-07T00:00:00Z', '2026-08-07T00:00:00Z')"
            )

        # Core + stat_* domains keep their integrity (Option A: no change to those).
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names), f"{table} missing UNIQUE {expected - names}"
        stat_unique = {uc["name"] for uc in insp.get_unique_constraints("stat_snapshots")}
        assert STAT_SNAPSHOT_UNIQUE.issubset(stat_unique)
    finally:
        engine.dispose()


def test_downgrade_0006_drops_only_feature_tables_core_stat_untouched(
    tmp_path: Path,
) -> None:
    """Downgrade from head to 0005 removes ONLY feature_*; core/import/stat_* survive."""
    db = tmp_path / "down_feature.db"
    cfg = _config(db)
    command.upgrade(cfg, "head")
    assert _domain_tables(db) == HEAD_TABLES

    command.downgrade(cfg, _REV_0005)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        # Exactly F1 + import + stat_* remain — no feature_* residue, no core loss.
        assert _domain_tables(db) == STAT_HEAD_TABLES
        # No feature_* index leaks.
        for name, (table, _columns) in FEATURE_INDEXES.items():
            if table in _domain_tables(db):  # pragma: no cover - defensive
                idx = {i["name"] for i in insp.get_indexes(table)}
                assert name not in idx, f"{name} leaked after downgrade"
        # stat_* integrity survives.
        stat_unique = {uc["name"] for uc in insp.get_unique_constraints("stat_snapshots")}
        assert STAT_SNAPSHOT_UNIQUE.issubset(stat_unique)
    finally:
        engine.dispose()


def test_upgrade_0007_creates_prob_tables_with_integrity_and_indexes(
    tmp_path: Path,
) -> None:
    """0007 adds the two prob_* tables (integrity + indexes); core/stat_*/feature_* untouched."""
    db = tmp_path / "up_prob.db"
    cfg = _config(db)
    command.upgrade(cfg, _REV_0007)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        assert _domain_tables(db) == HEAD_TABLES

        # prob_snapshots integrity: UNIQUE(...), CHECK(range/status), FK RESTRICT.
        unique = {uc["name"] for uc in insp.get_unique_constraints("prob_snapshots")}
        assert PROB_SNAPSHOT_UNIQUE.issubset(unique)
        checks = {ck["name"] for ck in insp.get_check_constraints("prob_snapshots")}
        assert PROB_SNAPSHOT_CHECKS.issubset(checks)
        fk_lottery = {
            fk["constrained_columns"][0] for fk in insp.get_foreign_keys("prob_snapshots")
        }
        assert "lottery_id" in fk_lottery

        # prob_values: surrogate id PK (D-A4) + FK to the header only, no FK to draw
        # (PES-03), nullable draw_number for grid rows, cell UNIQUE.
        pk = set(insp.get_pk_constraint("prob_values")["constrained_columns"])
        assert pk == {"id"}
        fk_cols = {
            col for fk in insp.get_foreign_keys("prob_values") for col in fk["constrained_columns"]
        }
        assert fk_cols == {"snapshot_id"}
        draw_cols = {col["name"]: col for col in insp.get_columns("prob_values")}
        assert draw_cols["draw_number"]["nullable"]
        pval_unique = {uc["name"] for uc in insp.get_unique_constraints("prob_values")}
        assert "uq_prob_values_cell" in pval_unique

        # All prob_* indexes exist with the correct columns (design Migration, PES-09).
        for name, (table, columns) in PROB_INDEXES.items():
            idx = {i["name"]: i for i in insp.get_indexes(table)}
            assert name in idx, f"missing index {name} on {table}"
            assert tuple(idx[name]["column_names"]) == columns
            assert not idx[name]["unique"]  # performance, not integrity

        # The status CHECK accepts 'failed' (PES-07 fail policy). Parent lottery first
        # so the FK RESTRICT does not block the snapshot row regardless of the SQLite
        # FK pragma default.
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO lottery (id, code, name, country, min_number, max_number,"
                " numbers_to_select, super_number_min, super_number_max, created_at)"
                " VALUES (1, 'L1', 'Lottery 1', 'AR', 1, 45, 5, NULL, NULL,"
                "  '2026-08-07T00:00:00Z')"
            )
            conn.exec_driver_sql(
                "INSERT INTO prob_snapshots"
                " (id, lottery_id, model_set, version, prob_generator_version, checksum,"
                "  input_fingerprint, status, is_locked, draw_count, draws_from, draws_to,"
                "  created_at, updated_at)"
                " VALUES (1, 1, 'core', '1', '1.0.0',"
                "  'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',"
                "  'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',"
                "  'failed', 0, 0, 0, 0,"
                "  '2026-08-07T00:00:00Z', '2026-08-07T00:00:00Z')"
            )

        # Core + stat_* + feature_* domains keep their integrity (no change to those).
        for table, expected in EXPECTED_UNIQUE.items():
            names = {uc["name"] for uc in insp.get_unique_constraints(table)}
            assert expected.issubset(names), f"{table} missing UNIQUE {expected - names}"
        stat_unique = {uc["name"] for uc in insp.get_unique_constraints("stat_snapshots")}
        assert STAT_SNAPSHOT_UNIQUE.issubset(stat_unique)
        feat_unique = {uc["name"] for uc in insp.get_unique_constraints("feature_snapshots")}
        assert FEATURE_SNAPSHOT_UNIQUE.issubset(feat_unique)
    finally:
        engine.dispose()


def test_downgrade_0007_drops_only_prob_tables_core_stat_feature_untouched(
    tmp_path: Path,
) -> None:
    """Downgrade from head to 0006 removes ONLY prob_*; all prior domains survive (PES-09)."""
    db = tmp_path / "down_prob.db"
    cfg = _config(db)
    command.upgrade(cfg, "head")
    assert _domain_tables(db) == HEAD_TABLES

    command.downgrade(cfg, _REV_0006)

    engine = sa.create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    try:
        # Exactly F1 + import + stat_* + feature_* remain — no prob_* residue, no core loss.
        assert _domain_tables(db) == FEATURE_HEAD_TABLES
        # No prob_* index leaks.
        for name, (table, _columns) in PROB_INDEXES.items():
            if table in _domain_tables(db):  # pragma: no cover - defensive
                idx = {i["name"] for i in insp.get_indexes(table)}
                assert name not in idx, f"{name} leaked after downgrade"
        # stat_* and feature_* integrity survive.
        stat_unique = {uc["name"] for uc in insp.get_unique_constraints("stat_snapshots")}
        assert STAT_SNAPSHOT_UNIQUE.issubset(stat_unique)
        feat_unique = {uc["name"] for uc in insp.get_unique_constraints("feature_snapshots")}
        assert FEATURE_SNAPSHOT_UNIQUE.issubset(feat_unique)
    finally:
        engine.dispose()
