"""StatSnapshot entity: immutable header of one statistics snapshot (design §2).

Header-only ORM: the metric payload rows live in the sibling ``stat_*`` tables
(``stat_frequency``, ``stat_frequency_positions``, ``stat_gaps``,
``stat_averages``, ``stat_scalars``), all FK'd to this row. Immutability is
enforced by the domain service (``is_locked`` guard + ``status`` flip), not by
the DB — same rationale as ``datasets`` (no dialect triggers, REQ-09 portable).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.lottery import Lottery


# The allowed snapshot statuses (design §3: active = current, retired = superseded,
# failed = generation that aborted mid-batch, never active/partial). DB owns the
# value domain via CHECK; the service transitions between them.
SNAPSHOT_STATUSES = ("active", "retired", "failed")


class StatSnapshot(Base):
    """One versioned, immutable statistics snapshot for a (lottery, metric_set).

    Exactly one row has ``status='active'`` per ``(lottery_id, metric_set)`` —
    enforced by the service in the same transaction that writes a new version
    (design §2/§7). ``version`` is the human monotonic number per
    (lottery, metric_set); ``generator_version`` is the algorithm identity (§8);
    ``checksum`` is the canonical SHA-256 determinism proof (C2/STE-05).
    """

    __tablename__ = "stat_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    metric_set: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draw_count: Mapped[int] = mapped_column(Integer, nullable=False)
    draws_from: Mapped[int] = mapped_column(Integer, nullable=False)
    draws_to: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        # One immutable version identity per (lottery, metric_set) — STE-11/STE-04.
        UniqueConstraint(
            "lottery_id", "metric_set", "version", name="uq_stat_snapshots_scope_version"
        ),
        CheckConstraint("draws_from <= draws_to", name="ck_stat_snapshots_range"),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')", name="ck_stat_snapshots_status"
        ),
    )
