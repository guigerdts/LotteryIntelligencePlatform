"""MetaRankingEntry entity: one scored model within a meta-learning ranking.

Parent FK to ``meta_rankings`` with RESTRICT lifecycle. Engine type
scoped to the four supported engines (META-015).
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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.meta_ranking import MetaRanking


class MetaRankingEntry(Base):
    """A scored model within a meta-learning ranking snapshot (META-005)."""

    __tablename__ = "meta_ranking_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ranking_id: Mapped[int] = mapped_column(
        ForeignKey("meta_rankings.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_type: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    ranking: Mapped[MetaRanking] = relationship()

    __table_args__ = (
        CheckConstraint(
            "engine_type IN ('backtesting', 'ml', 'dl', 'optimization')",
            name="ck_meta_ranking_entries_engine_type",
        ),
    )
