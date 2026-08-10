"""opt engine snapshots and best-params result table

Revision ID: 0011_opt_tables
Revises: 0010_dl_tables
Create Date: 2026-08-10

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_opt_tables"
down_revision: str | None = "0010_dl_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The OPT-engine header table (design Data Model, mirroring 0009/0010 snapshots).
# Immutable per (lottery, optimizer) with the objective metric/direction and search
# space recorded in the header because they participate in the input fingerprint
# (OE-03/04/07). ``algorithm_params`` stores optimizer-specific parameters;
# ``termination``/``termination_params`` record the stopping criteria (OE-06).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("optimizer", sa.String(length=32), nullable=False),
    sa.Column("model_set", sa.String(length=32), nullable=False),
    sa.Column("objective_metric", sa.String(length=32), nullable=False),
    sa.Column("objective_direction", sa.String(length=16), nullable=False),
    sa.Column("algorithm_params", sa.Text(), nullable=False),
    sa.Column("search_space", sa.Text(), nullable=False),
    sa.Column("termination", sa.String(length=16), nullable=False),
    sa.Column("termination_params", sa.Text(), nullable=True),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("is_locked", sa.Boolean(), nullable=False),
    sa.Column("draw_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id", "optimizer", "fingerprint", name="uq_opt_snapshots_scope_fingerprint"
    ),
    sa.CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_opt_snapshots_status"),
]

# Best-params result table: one row per target model per optimization run.
# ``best_fitness`` is Numeric(20,8) (float red line, OE-07); ``best_params``
# stores winning hyperparameters as JSON; ``convergence_history`` records the
# evaluation-by-evaluation fitness trajectory (OE-13).
# Surrogate ``id`` PK mirrors the ml_metrics/dl_metrics payload pattern.
_RESULTS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("target_model", sa.String(length=64), nullable=False),
    sa.Column("best_params", sa.Text(), nullable=False),
    sa.Column("best_fitness", sa.Numeric(20, 8), nullable=False),
    sa.Column("convergence_history", sa.Text(), nullable=True),
    sa.Column("metrics", sa.Text(), nullable=False),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["opt_snapshots.id"], ondelete="RESTRICT"),
]

# The two opt_* indexes (design Migration, OE-01): active-header resolution on the
# snapshot and the snapshot_id join on the results.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_osnap_lottery_optimizer_status", "opt_snapshots", ["lottery_id", "optimizer", "status"]),
    ("ix_oresult_snapshot_id", "opt_results", ["snapshot_id"]),
]


def upgrade() -> None:
    """Create ``opt_snapshots`` + ``opt_results`` and their indexes.

    Additive (REQ-09/OE-14): only the opt domain is touched; core, ``stat_*``,
    ``feature_*``, ``prob_*``, ``graph_*``, ``ml_*`` and ``dl_*`` stay byte-identical.
    """
    op.create_table("opt_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("opt_results", *tuple(_RESULTS_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``opt_*`` tables and their indexes; all other domains untouched.

    Non-destructive rollback (design Migration, OE-14): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``/``feature_*``/
    ``prob_*``/``graph_*``/``ml_*``/``dl_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("opt_results")
    op.drop_table("opt_snapshots")
