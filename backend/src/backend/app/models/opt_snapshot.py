"""OptSnapshot entity: immutable header of one optimization run (design, OE-01/10).

Header-only ORM mirroring ``MlSnapshot``/``DlSnapshot``: the normalized best-params
payload lives in the sibling ``opt_results`` table FK'd to this row. Immutability
is enforced by the domain service (``is_locked`` guard + ``status`` flip), never
by dialect triggers (REQ-09 portable). ``optimizer`` scopes the run (core-4: ga, pso,
bayesian, sa, OE-09); ``objective_metric``/``objective_direction`` record the
optimization objective (OE-03); ``search_space`` stores the JSON parameter ranges
(OE-04); ``fingerprint`` is the canonical SHA-256 invalidation key (OE-07).
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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.lottery import Lottery

# Lifecycle (design Snapshot Store & Service, OE-10, mirroring prior snapshots):
# active = current, retired = superseded, failed = optimization that aborted.
# DB owns the domain via CHECK.
OPT_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class OptSnapshot(Base):
    """One versioned, immutable optimization snapshot for a (lottery, optimizer).

    Exactly one row has ``status='active'`` per ``(lottery_id, optimizer)`` — enforced
    by the service in the same transaction that writes a new version (OE-10).
    ``version`` is the human monotonic number; ``optimizer`` is the algorithm identity
    (ga, pso, bayesian, sa); ``fingerprint`` is the canonical SHA-256 invalidation
    key (OE-07).
    """

    __tablename__ = "opt_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    optimizer: Mapped[str] = mapped_column(String(32), nullable=False)
    model_set: Mapped[str] = mapped_column(String(32), nullable=False)
    objective_metric: Mapped[str] = mapped_column(String(32), nullable=False, default="f1")
    objective_direction: Mapped[str] = mapped_column(String(16), nullable=False, default="maximize")
    algorithm_params: Mapped[str] = mapped_column(Text, nullable=False)
    search_space: Mapped[str] = mapped_column(Text, nullable=False)
    termination: Mapped[str] = mapped_column(String(16), nullable=False, default="fixed")
    termination_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draw_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        # One immutable version identity per (lottery, optimizer) — OE-10.
        UniqueConstraint(
            "lottery_id", "optimizer", "fingerprint", name="uq_opt_snapshots_scope_fingerprint"
        ),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')", name="ck_opt_snapshots_status"
        ),
    )
