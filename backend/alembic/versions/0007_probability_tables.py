"""probability engine snapshots and normalized payload tables

Revision ID: 0007_probability_tables
Revises: 0006_feature_tables
Create Date: 2026-08-08

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_probability_tables"
down_revision: str | None = "0006_feature_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The probability-engine header + payload tables (design Data Model, mirroring 0005/0006).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK. Performance indexes ship
# here as explicit CREATE INDEX (SQLite does not auto-index FKs) following 0002/0005/0006.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("model_set", sa.String(length=16), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("prob_generator_version", sa.String(length=32), nullable=False),
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
        "lottery_id", "model_set", "version", name="uq_prob_snapshots_scope_version"
    ),
    sa.CheckConstraint("draws_from <= draws_to", name="ck_prob_snapshots_range"),
    sa.CheckConstraint(
        "status IN ('active', 'retired', 'failed')", name="ck_prob_snapshots_status"
    ),
]

# Normalized payload: one probability value per (snapshot, model, version, subject,
# draw_number) — surrogate ``id`` PK because ``draw_number`` is NULLable on grid rows
# (D-A4), and NO FK to ``draw`` (PES-03, draw_number axis only, stat_*/feature_* parity).
_VALUES_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("model_id", sa.String(length=64), nullable=False),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.Column("subject", sa.String(length=64), nullable=False),
    sa.Column("draw_number", sa.Integer(), nullable=True),
    sa.Column("value", sa.Numeric(20, 8), nullable=False),
    sa.Column("params_json", sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["prob_snapshots.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "snapshot_id",
        "model_id",
        "model_version",
        "subject",
        "draw_number",
        name="uq_prob_values_cell",
    ),
]

# The three prob_* indexes (PES-09 names, design Migration): active-header resolution on
# the snapshot, snapshot_id join on the payload, and per-subject/quantile row reads.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_psnap_lottery_model_status", "prob_snapshots", ["lottery_id", "model_set", "status"]),
    ("ix_pval_snapshot_id", "prob_values", ["snapshot_id"]),
    ("ix_pval_subject", "prob_values", ["subject"]),
]


def upgrade() -> None:
    """Create ``prob_snapshots`` + ``prob_values`` and their three indexes.

    Additive (REQ-09): only the probability domain is touched; core, ``stat_*`` and
    ``feature_*`` stay byte-identical (PES-09). The revision is a leaf on 0006.
    """
    op.create_table("prob_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("prob_values", *tuple(_VALUES_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``prob_*`` tables and their indexes; core/stat_*/feature_* untouched.

    Non-destructive rollback (design Migration / PES-09): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``/``feature_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("prob_values")
    op.drop_table("prob_snapshots")
