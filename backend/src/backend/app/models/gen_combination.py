"""GenCombination entity: one generated lottery combination within a snapshot.

Parent FK to ``gen_snapshots`` with RESTRICT lifecycle. Numbers stored as
JSON text array. Score is nullable — NULL means "no evaluation" in MVP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.gen_snapshot import GenSnapshot


class GenCombination(Base):
    """A generated lottery combination within a generator snapshot."""

    __tablename__ = "gen_combinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("gen_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    numbers: Mapped[str] = mapped_column(Text, nullable=False)
    super_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    snapshot: Mapped[GenSnapshot] = relationship()
