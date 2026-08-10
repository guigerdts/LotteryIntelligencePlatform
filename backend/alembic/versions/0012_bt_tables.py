"""backtesting engine snapshots and results table

Revision ID: 0012_bt_tables
Revises: 0011_opt_tables
Create Date: 2026-08-10

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_bt_tables"
down_revision: str | None = "0011_opt_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The BT-engine header table (design Data Model, mirroring opt_* pattern).
# Immutable per (lottery, strategy) with the configuration recorded in the header
# because it participates in the input fingerprint (BTE-06/18).
# ``strategy_id`` identifies the strategy (e.g. 'ml-core-5', 'dl-core-3');
# ``config_json`` stores walk-forward configuration as JSON;
# ``fingerprint`` is the canonical SHA-256 invalidation key (BTE-06).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("strategy_id", sa.String(length=100), nullable=False),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("config_json", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint("fingerprint", name="uq_bt_snapshots_fingerprint"),
    sa.CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_bt_snapshots_status"),
]

# Results table: one row per backtest run.
# ``aggregate_metrics_json`` stores the overall MetricSet as JSON (BTE-08);
# ``window_history_json`` stores per-window WindowResult list as JSON (BTE-15).
# Surrogate ``id`` PK mirrors the opt_results/ml_metrics/dl_metrics pattern.
_RESULTS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("aggregate_metrics_json", sa.Text(), nullable=False),
    sa.Column("window_history_json", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["bt_snapshots.id"], ondelete="RESTRICT"),
]

# The two bt_* indexes (design Migration, BTE-01): active-header resolution on the
# snapshot and the snapshot_id join on the results.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_bt_snapshots_lottery_strategy", "bt_snapshots", ["lottery_id", "strategy_id"]),
    ("ix_bt_results_snapshot_id", "bt_results", ["snapshot_id"]),
]


def upgrade() -> None:
    """Create ``bt_snapshots`` + ``bt_results`` and their indexes.

    Additive (REQ-09/BTE-13): only the bt domain is touched; core, ``stat_*``,
    ``feature_*``, ``prob_*``, ``graph_*``, ``ml_*``, ``dl_*`` and ``opt_*``
    stay byte-identical.
    """
    op.create_table("bt_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("bt_results", *tuple(_RESULTS_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``bt_*`` tables and their indexes; all other domains untouched.

    Non-destructive rollback (design Migration, BTE-13): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``/``feature_*``/
    ``prob_*``/``graph_*``/``ml_*``/``dl_*``/``opt_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("bt_results")
    op.drop_table("bt_snapshots")
