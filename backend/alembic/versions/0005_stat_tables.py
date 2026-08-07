"""statistics snapshots and payload tables

Revision ID: 0005_stat_tables
Revises: 0004_import_performance_indexes
Create Date: 2026-08-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_stat_tables"
down_revision: str | None = "0004_import_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The statistics snapshot headers and their five payload tables (design §2).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK — mirroring 0001/0003.
# Performance indexes ship here as explicit CREATE INDEX (SQLite does not
# auto-index FKs), following the 0002/0004 pattern — one file owns both the
# bodies and the payload-snapshot join indexes (design §4 "Indexes" table).
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("metric_set", sa.String(length=16), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("generator_version", sa.String(length=32), nullable=False),
    sa.Column("engine_version", sa.String(length=32), nullable=False),
    sa.Column("checksum", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("is_locked", sa.Boolean(), nullable=False),
    sa.Column("draw_count", sa.Integer(), nullable=False),
    sa.Column("draws_from", sa.Integer(), nullable=False),
    sa.Column("draws_to", sa.Integer(), nullable=False),
    sa.Column("parser_version", sa.String(length=32), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "lottery_id", "metric_set", "version", name="uq_stat_snapshots_scope_version"
    ),
    sa.CheckConstraint("draws_from <= draws_to", name="ck_stat_snapshots_range"),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')", name="ck_stat_snapshots_status"
    ),
]

# Payload tables: composite PK on (snapshot_id, ...), FK RESTRICT to stat_snapshots.
_PAYLOAD_TABLES: dict[str, list[sa.Column]] = {
    "stat_frequency": [
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", "number"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["stat_snapshots.id"], ondelete="RESTRICT"),
    ],
    "stat_frequency_positions": [
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", "number", "position"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["stat_snapshots.id"], ondelete="RESTRICT"),
    ],
    "stat_gaps": [
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("min_gap", sa.Integer(), nullable=True),
        sa.Column("max_gap", sa.Integer(), nullable=True),
        sa.Column("avg_gap", sa.Numeric(20, 6), nullable=True),
        sa.PrimaryKeyConstraint("snapshot_id", "number"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["stat_snapshots.id"], ondelete="RESTRICT"),
    ],
    "stat_averages": [
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("series_key", sa.String(length=32), nullable=False),
        sa.Column("mean", sa.Numeric(20, 6), nullable=True),
        sa.Column("non_null_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", "series_key"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["stat_snapshots.id"], ondelete="RESTRICT"),
    ],
    "stat_scalars": [
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", "name"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["stat_snapshots.id"], ondelete="RESTRICT"),
    ],
}

# The six stat_* indexes (design §4: "Indexes" table): active-resolution on the
# header plus a snapshot_id join index on each payload. NO draw/draw_numbers /
# core-domain change (Option A — the core stays untouched).
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_snap_lottery_metric_status", "stat_snapshots", ["lottery_id", "metric_set", "status"]),
    ("ix_stat_frequency_snapshot_id", "stat_frequency", ["snapshot_id"]),
    ("ix_stat_frequency_positions_snapshot_id", "stat_frequency_positions", ["snapshot_id"]),
    ("ix_stat_gaps_snapshot_id", "stat_gaps", ["snapshot_id"]),
    ("ix_stat_averages_snapshot_id", "stat_averages", ["snapshot_id"]),
    ("ix_stat_scalars_snapshot_id", "stat_scalars", ["snapshot_id"]),
]


def upgrade() -> None:
    """Create the six ``stat_*`` tables plus their indexes (additive, REQ-09).

    Only portable ops; the stat domain is fully independent of F1/F2 tables, so
    this revision never touches ``draw``/``draw_numbers``/``datasets`` or any
    core table (Option A, design §4/§12).
    """
    op.create_table(
        "stat_snapshots",
        *tuple(_SNAPSHOT_TABLE),
    )
    for table, columns in _PAYLOAD_TABLES.items():
        op.create_table(table, *tuple(columns))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``stat_*`` tables and their indexes; core untouched (design §12)."""
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    for table in reversed(list(_PAYLOAD_TABLES)):
        op.drop_table(table)
    op.drop_table("stat_snapshots")
