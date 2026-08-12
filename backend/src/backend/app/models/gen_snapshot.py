"""GenSnapshot entity: immutable header of one generator run.

Scopes per (lottery_id, selection_id) with monotonic versioning and
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
    from backend.app.models.meta_selection import MetaSelection


class GenSnapshot(Base):
    """One versioned, immutable generator snapshot for a (lottery, selection)."""

    __tablename__ = "gen_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("meta_selections.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()
    selection: Mapped[MetaSelection] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "lottery_id",
            "selection_id",
            "fingerprint",
            name="uq_gen_snapshots_scope_fingerprint",
        ),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')",
            name="ck_gen_snapshots_status",
        ),
    )
