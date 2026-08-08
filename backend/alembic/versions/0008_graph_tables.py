"""graph engine snapshots and normalized payload tables

Revision ID: 0008_graph_tables
Revises: 0007_probability_tables
Create Date: 2026-08-08

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_graph_tables"
down_revision: str | None = "0007_probability_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The graph-engine header + payload tables (design Data Model, mirroring 0005/0006/0007).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK. Performance indexes ship
# here as explicit CREATE INDEX (SQLite does not auto-index FKs) following 0002/0005/0006.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("graph_type", sa.String(length=32), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("graph_generator_version", sa.String(length=32), nullable=False),
    sa.Column("checksum", sa.String(length=64), nullable=False),
    sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("params_json", sa.Text(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("is_locked", sa.Boolean(), nullable=False),
    sa.Column("draw_count", sa.Integer(), nullable=False),
    sa.Column("draws_from", sa.Integer(), nullable=False),
    sa.Column("draws_to", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id", "graph_type", "version", name="uq_graph_snapshots_scope_version"
    ),
    sa.CheckConstraint("draws_from <= draws_to", name="ck_graph_snapshots_range"),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')", name="ck_graph_snapshots_status"
    ),
]

# Normalized payload: one graph value per (snapshot, metric_type, subject, draw_number)
# — surrogate ``id`` PK because ``draw_number`` is NULLable on grid rows (D-A4),
# and NO FK to ``draw`` (draw_number axis only, stat_*/feature_*/prob_* parity).
_VALUES_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("metric_type", sa.String(length=32), nullable=False),
    sa.Column("subject", sa.String(length=64), nullable=False),
    sa.Column("draw_number", sa.Integer(), nullable=True),
    sa.Column("value", sa.Numeric(20, 8), nullable=False),
    sa.Column("params_json", sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["graph_snapshots.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "snapshot_id",
        "metric_type",
        "subject",
        "draw_number",
        name="uq_graph_values_cell",
    ),
]

# The three graph_* indexes (design Migration): active-header resolution on
# the snapshot, snapshot_id join on the payload, and per-metric_type/subject row reads.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_gsnap_lottery_type_status", "graph_snapshots", ["lottery_id", "graph_type", "status"]),
    ("ix_gval_snapshot_id", "graph_values", ["snapshot_id"]),
    ("ix_gval_metric_type", "graph_values", ["metric_type"]),
]


def upgrade() -> None:
    """Create ``graph_snapshots`` + ``graph_values`` and their three indexes.

    Additive (REQ-09): only the graph domain is touched; core, ``stat_*``,
    ``feature_*`` and ``prob_*`` stay byte-identical.
    """
    op.create_table("graph_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("graph_values", *tuple(_VALUES_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``graph_*`` tables and their indexes; core/stat_*/feature_*/prob_* untouched.

    Non-destructive rollback (design Migration): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``/``feature_*``/``prob_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("graph_values")
    op.drop_table("graph_snapshots")
