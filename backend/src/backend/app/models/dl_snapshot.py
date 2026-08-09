"""DlSnapshot entity: immutable header of one DL snapshot (design Data Model, DLE-01/08).

Header-only ORM mirroring ``MlSnapshot``: the normalized per-model metric payload
lives in the sibling ``dl_metrics`` table FK'd to this row. Immutability is enforced
by the domain service (``status`` flip), never by dialect triggers (REQ-09 portable).
``dl_generator_version`` is the DL engine's algorithm identity (independent of the
ML engine's ``ml_generator_version``, DLE-08); ``model_set`` scopes the run (only
``core-3`` executes, DLE-07) and ``cut`` records the walk-forward split boundary that
participates in the input fingerprint (DLE-04/08). ``input_fingerprint`` is the
canonical SHA-256 invalidation key; float NEVER enters any persisted value (DLE-08).
``window`` is the sequence length W (DLE-04), a fingerprint-affecting hyperparameter.
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

# Lifecycle (design Snapshot Store & Service, DLE-12, mirroring MlSnapshot):
# active = current, retired = superseded, failed = generation that aborted.
# DB owns the domain via CHECK.
DL_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class DlSnapshot(Base):
    """One versioned, immutable DL snapshot for a (lottery, model_set).

    Exactly one row has ``status='active'`` per ``(lottery_id, model_set)`` — enforced
    by the service in the same transaction that writes a new version (DLE-12).
    ``version`` is the human monotonic number; ``dl_generator_version`` is this
    engine's algorithm identity (independent of Statistics/Feature/Probability/Graph/ML,
    D-A6); ``checksum`` proves output determinism and ``input_fingerprint`` is the
    canonical SHA-256 invalidation key (DLE-08). ``window`` is the sequence length W
    (DLE-04), a fingerprint-affecting hyperparameter stored in the header.
    """

    __tablename__ = "dl_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_set: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    dl_generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    cut: Mapped[int] = mapped_column(Integer, nullable=False)
    window: Mapped[int] = mapped_column(Integer, nullable=False)
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
        # One immutable version identity per (lottery, model_set) — DLE-12.
        UniqueConstraint(
            "lottery_id", "model_set", "version", name="uq_dl_snapshots_scope_version"
        ),
        CheckConstraint("draws_from <= draws_to", name="ck_dl_snapshots_range"),
        CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_dl_snapshots_status"),
    )
