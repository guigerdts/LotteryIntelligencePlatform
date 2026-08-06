"""import engine audit tables

Revision ID: 0003_imports_audit
Revises: 0002_performance_indexes
Create Date: 2026-08-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_imports_audit"
down_revision: str | None = "0002_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the two import-engine audit tables with integrity constraints (IE-06/IE-03).

    Only portable structural ops (REQ-09/CD-08): PK, FK RESTRICT, CHECK — no
    explicit performance indexes (they ship in 0004, mirroring F1's 0001/0002
    split), so 0003 alone is functionally complete for correctness. Every run of
    the import engine, including rejected/partial/failed, gets one ``imports``
    row (IE-06); per-row Phase B failures land in ``import_errors`` (IE-03).
    """
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lottery_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_file", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("import_type", sa.String(length=16), nullable=False),
        sa.Column("started_by", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_processed_row", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('rejected', 'in_progress', 'completed', 'partial', 'failed')",
            name="ck_imports_status",
        ),
        sa.CheckConstraint(
            "import_type IN ('manual', 'cli', 'runner')",
            name="ck_imports_import_type",
        ),
        sa.CheckConstraint("total_rows >= 0", name="ck_imports_total_rows_non_negative"),
        sa.CheckConstraint("imported_rows >= 0", name="ck_imports_imported_rows_non_negative"),
        sa.CheckConstraint("skipped_rows >= 0", name="ck_imports_skipped_rows_non_negative"),
        sa.CheckConstraint("duplicate_rows >= 0", name="ck_imports_duplicate_rows_non_negative"),
        sa.CheckConstraint("error_rows >= 0", name="ck_imports_error_rows_non_negative"),
    )
    op.create_table(
        "import_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("draw_number", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("error_code", sa.String(length=32), nullable=False),
        sa.Column("raw_row", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    """Drop the two import tables in reverse dependency order (import_errors -> imports)."""
    op.drop_table("import_errors")
    op.drop_table("imports")
