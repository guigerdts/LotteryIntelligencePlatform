"""FeatureSnapshot entity: immutable header of one feature snapshot (design §2, FES-01).

Header-only ORM mirroring ``StatSnapshot``: the normalized payload rows live in the
sibling ``feature_values`` table FK'd to this row. Immutability is enforced by the
domain service (``is_locked`` guard + ``status`` flip), never by dialect triggers
(REQ-09 portable). ``feature_engine_version`` is independent of ``STATS_GENERATOR_VERSION``
(FES-04); ``input_fingerprint`` is the invalidation key (design §5).
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


# Lifecycle (design §7, mirroring stat_*): active = current, retired = superseded,
# failed = generation that aborted, never active/partial. DB owns the domain via CHECK.
FEATURE_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class FeatureSnapshot(Base):
    """One versioned, immutable feature snapshot for a (lottery, feature_set).

    Exactly one row has ``status='active'`` per ``(lottery_id, feature_set)`` — enforced
    by the service in the same transaction that writes a new version (design §7). ``version``
    is the human monotonic number; ``feature_engine_version`` is this engine's algorithm
    identity (independent of Statistics); ``checksum`` proves output determinism (FES-05).
    """

    __tablename__ = "feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    feature_set: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draw_count: Mapped[int] = mapped_column(Integer, nullable=False)
    draws_from: Mapped[int] = mapped_column(Integer, nullable=False)
    draws_to: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        # One immutable version identity per (lottery, feature_set) — design §2.
        UniqueConstraint(
            "lottery_id", "feature_set", "version", name="uq_feature_snapshots_scope_version"
        ),
        CheckConstraint("draws_from <= draws_to", name="ck_feature_snapshots_range"),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')", name="ck_feature_snapshots_status"
        ),
    )
