"""exp_comparisons.run_ids indexed lookup (EXP-009).

Adds a nullable ``run_ids`` column to ``exp_comparisons`` plus a composite
index ``(experiment_id, run_ids)`` for the idempotent compare lookup, and
backfills existing rows from ``comparison_json`` in bounded chunks. The JSON
payload remains the source of truth; ``run_ids`` is a denormalized key:
``",".join(str(i) for i in sorted(r["run_id"] for r in data["runs"]))``.
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from alembic import op

revision: str = "0016_exp_comparisons_run_ids"
down_revision: str | None = "0015_gen_tables"
branch_labels: str | None = None
depends_on: str | None = None

_BATCH = 500


def _run_ids_key(comparison_json: str) -> str:
    """Derive the canonical run_ids key from a comparison payload."""
    data = json.loads(comparison_json)
    return ",".join(str(i) for i in sorted(r["run_id"] for r in data["runs"]))


def _backfill(conn: sa.engine.Connection) -> None:
    """Chunked Python backfill of run_ids from comparison_json (EXP-009)."""
    while True:
        rows = (
            conn.execute(
                sa.text(
                    "SELECT id, comparison_json FROM exp_comparisons "
                    "WHERE run_ids IS NULL ORDER BY id LIMIT :batch"
                ),
                {"batch": _BATCH},
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        for row in rows:
            try:
                key = _run_ids_key(row["comparison_json"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue  # malformed legacy payload stays unkeyed
            conn.execute(
                sa.text("UPDATE exp_comparisons SET run_ids = :key WHERE id = :id"),
                {"key": key, "id": row["id"]},
            )
        conn.commit()


def upgrade() -> None:
    """Add the nullable run_ids column + composite index, then backfill."""
    op.add_column(
        "exp_comparisons",
        sa.Column("run_ids", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_exp_comparisons_run_ids",
        "exp_comparisons",
        ["experiment_id", "run_ids"],
    )
    conn = op.get_bind()
    _backfill(conn)


def downgrade() -> None:
    """Drop the index and column; run_ids data is derived, never authoritative."""
    op.drop_index("ix_exp_comparisons_run_ids", table_name="exp_comparisons")
    op.drop_column("exp_comparisons", "run_ids")
