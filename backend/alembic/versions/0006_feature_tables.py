"""feature engine snapshots and normalized payload tables

Revision ID: 0006_feature_tables
Revises: 0005_stat_tables
Create Date: 2026-08-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_feature_tables"
down_revision: str | None = "0005_stat_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The feature-engine header + payload tables (design §2, mirroring 0005).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK. Performance indexes ship
# here as explicit CREATE INDEX (SQLite does not auto-index FKs) following 0002/0005.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("feature_set", sa.String(length=32), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("feature_engine_version", sa.String(length=32), nullable=False),
    sa.Column("checksum", sa.String(length=64), nullable=False),
    sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
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
        "lottery_id", "feature_set", "version", name="uq_feature_snapshots_scope_version"
    ),
    sa.CheckConstraint("draws_from <= draws_to", name="ck_feature_snapshots_range"),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')", name="ck_feature_snapshots_status"
    ),
]

# Normalized payload: one feature value per (snapshot, feature, draw_number) — no FK
# to ``draw`` (FES-03, draw_number axis only, stat_* parity).
_VALUES_TABLE: Sequence[sa.Column] = [
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("feature_id", sa.String(length=64), nullable=False),
    sa.Column("feature_version", sa.String(length=32), nullable=False),
    sa.Column("draw_number", sa.Integer(), nullable=False),
    sa.Column("value", sa.Numeric(20, 8), nullable=False),
    sa.PrimaryKeyConstraint("snapshot_id", "feature_id", "draw_number"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["feature_snapshots.id"], ondelete="RESTRICT"),
]

# The three feature_* indexes (design §3 "Indexes" table): active-resolution on the
# header, snapshot_id join on the payload, and the per-feature draw_number series read.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_fsnap_lottery_set_status", "feature_snapshots", ["lottery_id", "feature_set", "status"]),
    ("ix_fval_snapshot_id", "feature_values", ["snapshot_id"]),
    ("ix_fval_feature_draw", "feature_values", ["feature_id", "draw_number"]),
]


def upgrade() -> None:
    """Create ``feature_snapshots`` + ``feature_values`` and their three indexes.

    Additive (REQ-09): only the feature domain is touched; core and ``stat_*`` stay
    byte-identical (design §12 / FES-01). The revision is a leaf on 0005.
    """
    op.create_table("feature_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("feature_values", *tuple(_VALUES_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``feature_*`` tables and their indexes; core/stat_* untouched.

    Non-destructive rollback (design §5 "Migration / Rollout"): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("feature_values")
    op.drop_table("feature_snapshots")
