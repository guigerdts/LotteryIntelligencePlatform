"""ExpExperiment entity: versioned experiment header (EXP-001/002).

Tracks experiment lifecycle per lottery with monotonic versioning and
SHA-256 fingerprint idempotency. Status transitions: active → retired | failed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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

# Lifecycle (design, EXP-001): active = current, retired = superseded, failed = error.
# DB owns the domain via CHECK.
EXP_EXPERIMENT_STATUSES = ("active", "retired", "failed")


class ExpExperiment(Base):
    """One versioned experiment tracked across engine runs (EXP-001/002).

    Scoped per lottery with natural key (lottery_id, name, fingerprint).
    Exactly one row has ``status='active'`` per ``(lottery_id, name)``
    — enforced by the service in the same transaction that writes a new version.
    """

    __tablename__ = "exp_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "lottery_id",
            "name",
            "fingerprint",
            name="uq_exp_experiments_scope_fingerprint",
        ),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')",
            name="ck_exp_experiments_status",
        ),
    )
