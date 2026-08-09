"""ml engine snapshots and normalized payload tables

Revision ID: 0009_ml_tables
Revises: 0008_graph_tables
Create Date: 2026-08-09

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_ml_tables"
down_revision: str | None = "0008_graph_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The ML-engine header table (design Data Model, mirroring 0005/0006/0007/0008).
# Immutable per (lottery, model_set) with the walk-forward ``cut`` recorded in the
# header because it participates in the input fingerprint (MLE-03). Note: unlike the
# graph header, ``ml_snapshots`` carries NO ``params_json`` — frozen hyperparameters
# live per-model in ``ml_metrics.params_json`` (design Data Model; MLE-01).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("model_set", sa.String(length=32), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("ml_generator_version", sa.String(length=32), nullable=False),
    sa.Column("checksum", sa.String(length=64), nullable=False),
    sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("cut", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("is_locked", sa.Boolean(), nullable=False),
    sa.Column("draw_count", sa.Integer(), nullable=False),
    sa.Column("draws_from", sa.Integer(), nullable=False),
    sa.Column("draws_to", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint("lottery_id", "model_set", "version", name="uq_ml_snapshots_scope_version"),
    sa.CheckConstraint("draws_from <= draws_to", name="ck_ml_snapshots_range"),
    sa.CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_ml_snapshots_status"),
]

# Normalized payload: one Decimal-quantized metric cell per (snapshot, model,
# number, metric_name) — MLE-01/M-A7. ``value`` is Numeric(20,8) (float red line,
# MLE-05); ``params_json`` holds frozen hyperparameters only, never weights (MLE-01).
# Surrogate ``id`` PK mirrors the prob_*/graph_* payload pattern.
_METRICS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("model_id", sa.String(length=64), nullable=False),
    sa.Column("model_version", sa.String(length=32), nullable=False),
    sa.Column("number", sa.Integer(), nullable=False),
    sa.Column("metric_name", sa.String(length=32), nullable=False),
    sa.Column("value", sa.Numeric(20, 8), nullable=False),
    sa.Column("params_json", sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["ml_snapshots.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "snapshot_id",
        "model_id",
        "number",
        "metric_name",
        name="uq_ml_metrics_cell",
    ),
]

# The two ml_* indexes (design Migration, MLE-01): active-header resolution on the
# snapshot and the snapshot_id join on the payload.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_msnap_lottery_model_status", "ml_snapshots", ["lottery_id", "model_set", "status"]),
    ("ix_mval_snapshot_model_id", "ml_metrics", ["snapshot_id", "model_id"]),
]


def upgrade() -> None:
    """Create ``ml_snapshots`` + ``ml_metrics`` and their two indexes.

    Additive (REQ-09/MLE-10): only the ml domain is touched; core, ``stat_*``,
    ``feature_*``, ``prob_*`` and ``graph_*`` stay byte-identical.
    """
    op.create_table("ml_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("ml_metrics", *tuple(_METRICS_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``ml_*`` tables and their indexes; all other domains untouched.

    Non-destructive rollback (design Migration, MLE-10): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``/``feature_*``/
    ``prob_*``/``graph_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("ml_metrics")
    op.drop_table("ml_snapshots")
