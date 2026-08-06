"""ImportJob entity: one auditable import run of a source CSV (IE-06, design §4).

Records every execution of the import engine — including rejected, partial and
failed runs — so the audit trail is complete and reproducible. Structural-only:
columns, PK/FK, CHECK constraints and relationships (loading only); the state
machine is owned by ``ImportService`` (D-E) with the repository as a conditional
backstop, never by this model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.import_error import ImportError
    from backend.app.models.lottery import Lottery

# The allowed run statuses (CD-06 split: DB owns the value domain, the service
# owns legal transitions). Mirrors the design §4 state machine.
IMPORT_STATUSES = ("rejected", "in_progress", "completed", "partial", "failed")
# Channel-derived import channels (IE-07 / D-C): never client-supplied.
IMPORT_TYPES = ("manual", "cli", "runner")


class ImportJob(Base):
    """One import execution with its outcome counters (audit contract IE-06).

    ``lottery_id`` FK RESTRICT and every run is recorded; ``last_processed_row``
    is an additive resume marker (D-D / IE-06 "AT MINIMUM"). Timestamps are
    tz-aware UTC (CD-04). Structural-only — no transition logic lives here.
    """

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    import_type: Mapped[str] = mapped_column(String(16), nullable=False)
    started_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_processed_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship(back_populates="import_jobs")
    errors: Mapped[list[ImportError]] = relationship(back_populates="import_job")

    __table_args__ = (
        # Structural allowed value sets (CD-06: DB owns values, app owns transitions).
        CheckConstraint(
            "status IN ('rejected', 'in_progress', 'completed', 'partial', 'failed')",
            name="ck_imports_status",
        ),
        CheckConstraint(
            "import_type IN ('manual', 'cli', 'runner')",
            name="ck_imports_import_type",
        ),
        # Counter reconciliation floor: never negative (IE-06 total=import+skip+dup+error).
        CheckConstraint("total_rows >= 0", name="ck_imports_total_rows_non_negative"),
        CheckConstraint("imported_rows >= 0", name="ck_imports_imported_rows_non_negative"),
        CheckConstraint("skipped_rows >= 0", name="ck_imports_skipped_rows_non_negative"),
        CheckConstraint("duplicate_rows >= 0", name="ck_imports_duplicate_rows_non_negative"),
        CheckConstraint("error_rows >= 0", name="ck_imports_error_rows_non_negative"),
    )
