"""StatFrequency entity: per-number overall frequency payload rows (design §2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.stat_snapshot import StatSnapshot


class StatFrequency(Base):
    """One ``(number, count)`` row of a snapshot's overall frequency distribution.

    ``count`` is the exact INTEGER appearances of ``number`` across the snapshot's
    draw range (deterministic accumulation, design §2).
    """

    __tablename__ = "stat_frequency"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("stat_snapshots.id", ondelete="RESTRICT"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)

    snapshot: Mapped[StatSnapshot] = relationship()
