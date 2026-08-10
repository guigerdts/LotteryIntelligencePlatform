"""experiment engine tables

Revision ID: 0013_exp_tables
Revises: 0012_bt_tables
Create Date: 2026-08-10

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_exp_tables"
down_revision: str | None = "0012_bt_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Experiment header table (design Data Model, EXP-001/002).
# Scoped per lottery with natural key (lottery_id, name) plus fingerprint
# for idempotent versioning. Status lifecycle: active → retired | failed.
_EXPERIMENTS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("name", sa.String(length=200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("config_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id",
        "name",
        "fingerprint",
        name="uq_exp_experiments_scope_fingerprint",
    ),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')",
        name="ck_exp_experiments_status",
    ),
]

# Run association table (design Data Model, EXP-003).
# Links experiment to engine snapshots via polymorphic (engine_type, engine_snapshot_id).
# No DB FK to engine tables — service validates references.
_RUNS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("experiment_id", sa.Integer(), nullable=False),
    sa.Column("run_label", sa.String(length=100), nullable=False),
    sa.Column("engine_type", sa.String(length=20), nullable=False),
    sa.Column("engine_snapshot_id", sa.Integer(), nullable=False),
    sa.Column("engine_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(
        ["experiment_id"],
        ["exp_experiments.id"],
        ondelete="RESTRICT",
    ),
    sa.CheckConstraint(
        "engine_type IN ('backtesting', 'ml', 'dl', 'optimization')",
        name="ck_exp_runs_engine_type",
    ),
]

# Comparison persistence table (design Data Model, EXP-005).
# Immutable JSON snapshot of cross-run comparison results.
_COMPARISONS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("experiment_id", sa.Integer(), nullable=False),
    sa.Column("comparison_json", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(
        ["experiment_id"],
        ["exp_experiments.id"],
        ondelete="RESTRICT",
    ),
]

# Indexes (design Migration): lottery+status lookup and experiment FK joins.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_exp_experiments_lottery_status", "exp_experiments", ["lottery_id", "status"]),
    ("ix_exp_runs_experiment", "exp_runs", ["experiment_id"]),
    ("ix_exp_comparisons_experiment", "exp_comparisons", ["experiment_id"]),
]


def upgrade() -> None:
    """Create ``exp_experiments``, ``exp_runs``, ``exp_comparisons`` and indexes.

    Additive (REQ-09): only the exp domain is touched; all other domains
    stay byte-identical.
    """
    op.create_table("exp_experiments", *tuple(_EXPERIMENTS_TABLE))
    op.create_table("exp_runs", *tuple(_RUNS_TABLE))
    op.create_table("exp_comparisons", *tuple(_COMPARISONS_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``exp_*`` tables and indexes; all other domains untouched.

    Non-destructive rollback: the revert never touches core, ``stat_*``,
    ``feature_*``, ``prob_*``, ``graph_*``, ``ml_*``, ``dl_*``, ``opt_*``,
    or ``bt_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("exp_comparisons")
    op.drop_table("exp_runs")
    op.drop_table("exp_experiments")
