"""ProbSnapshot entity: immutable header of one probability snapshot (design Data Model, PES-01).

Header-only ORM mirroring ``StatSnapshot``/``FeatureSnapshot``: the normalized payload
rows live in the sibling ``prob_values`` table FK'd to this row. Immutability is enforced
by the domain service (``is_locked`` guard + ``status`` flip), never by dialect triggers
(REQ-09 portable). ``prob_generator_version`` is independent of ``STATS_GENERATOR_VERSION``
and ``feature_engine_version`` (PES-04); ``input_fingerprint`` is the invalidation key
(design Seed/Determinism, PES-05).
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


# Lifecycle (design Snapshot Store & Service, PES-07, mirroring stat_*/feature_*):
# active = current, retired = superseded, failed = generation that aborted, never
# active/partial. DB owns the domain via CHECK.
PROB_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class ProbSnapshot(Base):
    """One versioned, immutable probability snapshot for a (lottery, model_set).

    Exactly one row has ``status='active'`` per ``(lottery_id, model_set)`` — enforced
    by the service in the same transaction that writes a new version (PES-07). ``version``
    is the human monotonic number; ``prob_generator_version`` is this engine's algorithm
    identity (independent of Statistics/Feature, PES-04); ``checksum`` proves output
    determinism and ``input_fingerprint`` is the canonical SHA-256 invalidation key
    (PES-05).
    """

    __tablename__ = "prob_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_set: Mapped[str] = mapped_column(String(16), nullable=False, default="core")
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    prob_generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
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
        # One immutable version identity per (lottery, model_set) — PES-01/PES-07.
        UniqueConstraint(
            "lottery_id", "model_set", "version", name="uq_prob_snapshots_scope_version"
        ),
        CheckConstraint("draws_from <= draws_to", name="ck_prob_snapshots_range"),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')", name="ck_prob_snapshots_status"
        ),
    )
