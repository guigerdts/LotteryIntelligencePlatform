"""meta learning tables

Revision ID: 0014_meta_tables
Revises: 0013_exp_tables
Create Date: 2026-08-11

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_meta_tables"
down_revision: str | None = "0013_exp_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- meta_rankings (META-015) ---
_META_RANKINGS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("context_hash", sa.String(length=64), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("config_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id",
        "context_hash",
        "fingerprint",
        name="uq_meta_rankings_scope_fingerprint",
    ),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')",
        name="ck_meta_rankings_status",
    ),
]

# --- meta_ranking_entries (META-015) ---
_META_RANKING_ENTRIES_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("ranking_id", sa.Integer(), nullable=False),
    sa.Column("model_id", sa.String(length=100), nullable=False),
    sa.Column("engine_type", sa.String(length=20), nullable=False),
    sa.Column("score", sa.Float(), nullable=False),
    sa.Column("metrics_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(
        ["ranking_id"],
        ["meta_rankings.id"],
        ondelete="RESTRICT",
    ),
    sa.CheckConstraint(
        "engine_type IN ('backtesting', 'ml', 'dl', 'optimization')",
        name="ck_meta_ranking_entries_engine_type",
    ),
]

# --- meta_selections (META-015) ---
_META_SELECTIONS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("context_hash", sa.String(length=64), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("config_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id",
        "context_hash",
        "fingerprint",
        name="uq_meta_selections_scope_fingerprint",
    ),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')",
        name="ck_meta_selections_status",
    ),
]

# --- meta_selection_entries (META-015) ---
_META_SELECTION_ENTRIES_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("selection_id", sa.Integer(), nullable=False),
    sa.Column("ranking_id", sa.Integer(), nullable=False),
    sa.Column("model_id", sa.String(length=100), nullable=False),
    sa.Column("engine_type", sa.String(length=20), nullable=False),
    sa.Column("rank", sa.Integer(), nullable=False),
    sa.Column("score", sa.Float(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(
        ["selection_id"],
        ["meta_selections.id"],
        ondelete="RESTRICT",
    ),
    sa.ForeignKeyConstraint(
        ["ranking_id"],
        ["meta_rankings.id"],
        ondelete="RESTRICT",
    ),
    sa.CheckConstraint(
        "engine_type IN ('backtesting', 'ml', 'dl', 'optimization')",
        name="ck_meta_selection_entries_engine_type",
    ),
]

# Indexes (META-015): context lookup and FK joins.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_meta_rankings_lottery_context", "meta_rankings", ["lottery_id", "context_hash"]),
    ("ix_meta_ranking_entries_ranking", "meta_ranking_entries", ["ranking_id"]),
    ("ix_meta_selections_lottery_context", "meta_selections", ["lottery_id", "context_hash"]),
    ("ix_meta_selection_entries_selection", "meta_selection_entries", ["selection_id"]),
]


def upgrade() -> None:
    """Create meta_rankings, meta_ranking_entries, meta_selections, meta_selection_entries.

    Additive migration (META-015): only the meta domain is touched; all other
    domains stay byte-identical.
    """
    op.create_table("meta_rankings", *tuple(_META_RANKINGS_TABLE))
    op.create_table("meta_ranking_entries", *tuple(_META_RANKING_ENTRIES_TABLE))
    op.create_table("meta_selections", *tuple(_META_SELECTIONS_TABLE))
    op.create_table("meta_selection_entries", *tuple(_META_SELECTION_ENTRIES_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the meta_* tables and indexes; all other domains untouched.

    Non-destructive rollback: the revert never touches core, stat_*,
    feature_*, prob_*, graph_*, ml_*, dl_*, opt_* bt_*, or exp_*.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("meta_selection_entries")
    op.drop_table("meta_selections")
    op.drop_table("meta_ranking_entries")
    op.drop_table("meta_rankings")
