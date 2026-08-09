"""MlSnapshot entity: immutable header of one ML snapshot (design Data Model, MLE-01/08).

Header-only ORM mirroring ``StatSnapshot``/``FeatureSnapshot``/``ProbSnapshot``/
``GraphSnapshot``: the normalized per-model metric payload lives in the sibling
``ml_metrics`` table FK'd to this row. Immutability is enforced by the domain service
(``is_locked`` guard + ``status`` flip), never by dialect triggers (REQ-09 portable).
``ml_generator_version`` is the ML engine's algorithm identity (independent of every
other engine's version constant, MLE-05); ``model_set`` scopes the run (only
``core-5`` executes, MLE-07) and ``cut`` records the walk-forward split boundary that
participates in the input fingerprint (MLE-03). ``input_fingerprint`` is the canonical
SHA-256 invalidation key; float NEVER enters any persisted value (MLE-05/D4).
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

# Lifecycle (design Snapshot Store & Service, MLE-08, mirroring prior snapshots):
# active = current, retired = superseded, failed = generation that aborted, never
# active/partial. DB owns the domain via CHECK.
ML_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class MlSnapshot(Base):
    """One versioned, immutable ML snapshot for a (lottery, model_set).

    Exactly one row has ``status='active'`` per ``(lottery_id, model_set)`` — enforced
    by the service in the same transaction that writes a new version (MLE-08).
    ``version`` is the human monotonic number; ``ml_generator_version`` is this
    engine's algorithm identity (independent of Statistics/Feature/Probability/Graph,
    M-A6); ``checksum`` proves output determinism and ``input_fingerprint`` is the
    canonical SHA-256 invalidation key (MLE-05).
    """

    __tablename__ = "ml_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_set: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    ml_generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    cut: Mapped[int] = mapped_column(Integer, nullable=False)
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
        # One immutable version identity per (lottery, model_set) — MLE-08.
        UniqueConstraint(
            "lottery_id", "model_set", "version", name="uq_ml_snapshots_scope_version"
        ),
        CheckConstraint("draws_from <= draws_to", name="ck_ml_snapshots_range"),
        CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_ml_snapshots_status"),
    )
