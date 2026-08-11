"""MetaSelectionEntry entity: one selected model within a meta-learning selection.

Parent FK to ``meta_selections`` and ``meta_rankings`` with RESTRICT lifecycle.
Includes rank position within the selection (META-006).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.meta_ranking import MetaRanking
    from backend.app.models.meta_selection import MetaSelection


class MetaSelectionEntry(Base):
    """A selected model within a meta-learning selection snapshot (META-006)."""

    __tablename__ = "meta_selection_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("meta_selections.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    ranking_id: Mapped[int] = mapped_column(
        ForeignKey("meta_rankings.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    selection: Mapped[MetaSelection] = relationship()
    ranking: Mapped[MetaRanking] = relationship()

    __table_args__ = (
        CheckConstraint(
            "engine_type IN ('backtesting', 'ml', 'dl', 'optimization')",
            name="ck_meta_selection_entries_engine_type",
        ),
    )
