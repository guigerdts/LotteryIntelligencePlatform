"""dl engine snapshots, normalized payload tables, and weights blob table

Revision ID: 0010_dl_tables
Revises: 0009_ml_tables
Create Date: 2026-08-09

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_dl_tables"
down_revision: str | None = "0009_ml_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The DL-engine header table (design Data Model, mirroring 0009 ml_snapshots).
# Immutable per (lottery, model_set) with the walk-forward ``cut`` and sequence
# length ``window`` recorded in the header because they participate in the input
# fingerprint (DLE-04/08). Unlike ml_snapshots, ``window`` is a fingerprint-affecting
# hyperparameter stored directly in the header (DLE-04).
# Portable DDL only (REQ-09): PK, FK RESTRICT, UNIQUE, CHECK.
_SNAPSHOT_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("lottery_id", sa.Integer(), nullable=False),
    sa.Column("model_set", sa.String(length=32), nullable=False),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("dl_generator_version", sa.String(length=32), nullable=False),
    sa.Column("checksum", sa.String(length=64), nullable=False),
    sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("cut", sa.Integer(), nullable=False),
    sa.Column("window", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("is_locked", sa.Boolean(), nullable=False),
    sa.Column("draw_count", sa.Integer(), nullable=False),
    sa.Column("draws_from", sa.Integer(), nullable=False),
    sa.Column("draws_to", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint("lottery_id", "model_set", "version", name="uq_dl_snapshots_scope_version"),
    sa.CheckConstraint("draws_from <= draws_to", name="ck_dl_snapshots_range"),
    sa.CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_dl_snapshots_status"),
]

# Normalized payload: one Decimal-quantized metric cell per (snapshot, model,
# number, metric_name) — DLE-01/D-A7. ``value`` is Numeric(20,8) (float red line,
# DLE-08); ``params_json`` holds frozen hyperparameters only, including architecture
# config and training params.
# Surrogate ``id`` PK mirrors the ml_metrics/prob_*/graph_* payload pattern.
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
    sa.ForeignKeyConstraint(["snapshot_id"], ["dl_snapshots.id"], ondelete="RESTRICT"),
    sa.UniqueConstraint(
        "snapshot_id",
        "model_id",
        "number",
        "metric_name",
        name="uq_dl_metrics_cell",
    ),
]

# Weights blob table: one serialized model weights BLOB per (snapshot, model_id).
# Custom format: magic + format_version + fingerprint + tensor manifest + raw
# float32 LE + SHA-256; no pickle/joblib (DLE-09). Size limited to 16 MiB by
# CHECK constraint and validated at write time.
_WEIGHTS_TABLE: Sequence[sa.Column] = [
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column("snapshot_id", sa.Integer(), nullable=False),
    sa.Column("model_id", sa.String(length=64), nullable=False),
    sa.Column("weights_blob", sa.LargeBinary(), nullable=False),
    sa.Column("weights_size_bytes", sa.Integer(), nullable=False),
    sa.Column("weights_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("format_version", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("id"),
    sa.ForeignKeyConstraint(["snapshot_id"], ["dl_snapshots.id"], ondelete="RESTRICT"),
    sa.CheckConstraint("weights_size_bytes <= 16777216", name="ck_dl_weights_max_size"),
]

# The three dl_* indexes (design Migration, DLE-01): active-header resolution on the
# snapshot and the snapshot_id join on the payload.
_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_dsnap_lottery_model_status", "dl_snapshots", ["lottery_id", "model_set", "status"]),
    ("ix_dval_snapshot_model_id", "dl_metrics", ["snapshot_id", "model_id"]),
    ("ix_dweight_snapshot_model_id", "dl_weights", ["snapshot_id", "model_id"]),
]


def upgrade() -> None:
    """Create ``dl_snapshots`` + ``dl_metrics`` + ``dl_weights`` and their indexes.

    Additive (REQ-09/DLE-16): only the dl domain is touched; core, ``stat_*``,
    ``feature_*``, ``prob_*``, ``graph_*`` and ``ml_*`` stay byte-identical.
    """
    op.create_table("dl_snapshots", *tuple(_SNAPSHOT_TABLE))
    op.create_table("dl_metrics", *tuple(_METRICS_TABLE))
    op.create_table("dl_weights", *tuple(_WEIGHTS_TABLE))
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the ``dl_*`` tables and their indexes; all other domains untouched.

    Non-destructive rollback (design Migration, DLE-16): the revert never touches
    ``draw``/``draw_numbers``/``datasets``/``imports``/``stat_*``/``feature_*``/
    ``prob_*``/``graph_*``/``ml_*``.
    """
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_table("dl_weights")
    op.drop_table("dl_metrics")
    op.drop_table("dl_snapshots")
