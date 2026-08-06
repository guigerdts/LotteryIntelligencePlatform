"""initial core domain

Revision ID: 0001_initial_core_domain
Revises:
Create Date: 2026-08-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_core_domain"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the six core-domain tables in dependency order (REQ-09, CD-01..05).

    Only portable operations and structural constraints: PK, FK (RESTRICT),
    UNIQUE and CHECK. No performance indexes here — they ship in 0002 (PR-5),
    so 0002 stays functionally optional (user rule: 0001 owns integrity only).
    """
    op.create_table(
        "lottery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("min_number", sa.Integer(), nullable=False),
        sa.Column("max_number", sa.Integer(), nullable=False),
        sa.Column("numbers_to_select", sa.Integer(), nullable=False),
        sa.Column("super_number_min", sa.Integer(), nullable=True),
        sa.Column("super_number_max", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_lottery_code"),
        sa.CheckConstraint("min_number < max_number", name="ck_lottery_min_max"),
        sa.CheckConstraint(
            "numbers_to_select <= max_number - min_number + 1",
            name="ck_lottery_numbers_to_select",
        ),
        sa.CheckConstraint(
            "super_number_min IS NULL OR super_number_max IS NULL"
            " OR super_number_min <= super_number_max",
            name="ck_lottery_super_range",
        ),
    )
    op.create_table(
        "draw",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lottery_id", sa.Integer(), nullable=False),
        sa.Column("draw_number", sa.Integer(), nullable=False),
        sa.Column("draw_date", sa.Date(), nullable=False),
        sa.Column("jackpot", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("winners", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("lottery_id", "draw_number", name="uq_draw_lottery_draw_number"),
    )
    op.create_table(
        "draw_numbers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draw_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["draw_id"], ["draw.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("draw_id", "position", name="uq_draw_numbers_draw_position"),
        sa.UniqueConstraint("draw_id", "number", name="uq_draw_numbers_draw_number"),
    )
    op.create_table(
        "super_number",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draw_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["draw_id"], ["draw.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("draw_id", name="uq_super_number_draw_id"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lottery_id", sa.Integer(), nullable=False),
        sa.Column("filters", sa.Text(), nullable=True),
        sa.Column("generator_version", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lottery_id"], ["lottery.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("version", name="uq_datasets_version"),
    )
    op.create_table(
        "dataset_draws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("draw_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["draw_id"], ["draw.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("dataset_id", "draw_id", name="uq_dataset_draws_pair"),
    )


def downgrade() -> None:
    """Drop the six tables in reverse dependency order."""
    op.drop_table("dataset_draws")
    op.drop_table("datasets")
    op.drop_table("super_number")
    op.drop_table("draw_numbers")
    op.drop_table("draw")
    op.drop_table("lottery")
