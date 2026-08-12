"""generator tables

Revision ID: 0015_gen_tables
Revises: 0014_meta_tables
Create Date: 2026-08-11

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_gen_tables"
down_revision: str | None = "0014_meta_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# --- gen_snapshots (GEN-012) ---
_GEN_SNAPSHOTS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("selection_id", sa.Integer(), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("fingerprint", sa.String(length=64), nullable=False),
    sa.Column("config_json", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.ForeignKeyConstraint(["selection_id"], ["meta_selections.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id",
        "selection_id",
        "fingerprint",
        name="uq_gen_snapshots_scope_fingerprint",
    ),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')",
        name="ck_gen_snapshots_status",
    ),
]

# --- gen_combinations (GEN-012) ---
_GEN_COMBINATIONS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Column("numbers", sa.Text(), nullable=False),
    sa.Column("super_number", sa.Integer(), nullable=True),
    sa.Column("score", sa.Float(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["gen_snapshots.id"], ondelete="RESTRICT"),
]

# Indexes (GEN-012): FK joins and lookup.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_gen_snapshots_lottery_selection", "gen_snapshots", ["lottery_id", "selection_id"]),
    ("ix_gen_combinations_snapshot", "gen_combinations", ["snapshot_id"]),
]


def upgrade() -> None:
    """Create gen_snapshots and gen_combinations.

    Additive migration (GEN-012): only the generator domain is touched; all other
    domains stay byte-identical.
    """
    op.create_table("gen_snapshots", *tuple(_GEN_SNAPSHOTS_TABLE))
    op.create_table("gen_combinations", *tuple(_GEN_COMBINATIONS_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the gen_* tables and indexes; all other domains untouched.

    Non-destructive rollback: the revert never touches core, stat_*,
    feature_*, prob_*, graph_*, ml_*, dl_*, opt_* bt_*, exp_*, or meta_*.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("gen_combinations")
    op.drop_table("gen_snapshots")
