"""import performance indexes

Revision ID: 0004_import_performance_indexes
Revises: 0003_imports_audit
Create Date: 2026-08-06

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_import_performance_indexes"
down_revision: str | None = "0003_imports_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The three import performance indexes (design §4 Indexes table, Performance row),
# each an explicit CREATE INDEX so it is portable AND effective on SQLite, which
# does not auto-index foreign-key columns. 0004 is strictly additive and
# functionally optional: the application behaves identically with only 0003
# applied, merely slower on these paths (mirrors F1's 0002 split).
_INDEXES: list[tuple[str, str, list[str]]] = [
    # Latest-run lookup, the in-progress D-J guard and per-lottery history
    # (lottery_id as leading column also serves the FK join on SQLite).
    ("ix_imports_lottery_status_started", "imports", ["lottery_id", "status", "started_at"]),
    # Exact-same-file audit correlation (IE-04 / D-H checksum re-import).
    ("ix_imports_checksum", "imports", ["checksum"]),
    # per-run error listing (import_errors.import_id FK, IE-03).
    ("ix_import_errors_import_id", "import_errors", ["import_id"]),
]


def upgrade() -> None:
    """Add the three import performance indexes (portable, batch-mode compatible)."""
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    """Drop only the three performance indexes added by this revision."""
    for name, table, _columns in _INDEXES:
        op.drop_index(name, table_name=table)
