"""MetaSelection entity: immutable header of one meta-learning selection run.

Scopes per (lottery_id, context_hash) with monotonic versioning and
SHA-256 fingerprint idempotency. Status lifecycle: active | retired | failed.
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


class MetaSelection(Base):
    """One versioned, immutable meta-learning selection for a (lottery, context)."""

    __tablename__ = "meta_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "lottery_id",
            "context_hash",
            "fingerprint",
            name="uq_meta_selections_scope_fingerprint",
        ),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')",
            name="ck_meta_selections_status",
        ),
    )
