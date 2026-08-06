"""performance indexes

Revision ID: 0002_performance_indexes
Revises: 0001_initial_core_domain
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_performance_indexes"
down_revision: str | None = "0001_initial_core_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The four performance indexes (design Indexes table, Performance row), each an
# explicit CREATE INDEX so it is portable AND effective on SQLite, which does not
# auto-index foreign-key columns. 0002 is strictly additive and functionally
# optional: it changes no table, column, constraint or contract — the application
# behaves identically with only 0001 applied, merely slower on these paths.
_INDEXES: list[tuple[str, str, list[str]]] = [
    # Draw list filtered by `?lottery=` + date range (API_SPEC §19, CD-07).
    ("ix_draw_lottery_date", "draw", ["lottery_id", "draw_date"]),
    # draw.lottery_id FK joins (SQLite does not auto-index FKs).
    ("ix_draw_lottery_id", "draw", ["lottery_id"]),
    # draw_numbers.draw_id children load during serialization (CD-07).
    ("ix_draw_numbers_draw_id", "draw_numbers", ["draw_id"]),
    # dataset_draws.draw_id composition joins + reverse draw→dataset lookups.
    ("ix_dataset_draws_draw_id", "dataset_draws", ["draw_id"]),
]


def upgrade() -> None:
    """Add the four performance indexes (portable, batch-mode compatible)."""
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the four performance indexes added by this revision."""
    for name, table, _columns in _INDEXES:
        op.drop_index(name, table_name=table)
