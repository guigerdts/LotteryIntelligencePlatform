"""StatGap entity: per-number gap summary payload rows (design §2)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.stat_snapshot import StatSnapshot


class StatGap(Base):
    """One ``(number, gap_summary)`` row (design §2, STE-03).

    ``avg_gap`` is a `Decimal` mean over non-empty gap series; when a number has
    no observed gap (appears never/once) ``count=0`` and ``min``/``max``/``avg``
    are ``None`` (D4-style, never synthesized).
    """

    __tablename__ = "stat_gaps"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("stat_snapshots.id", ondelete="RESTRICT"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    min_gap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_gap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_gap: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)

    snapshot: Mapped[StatSnapshot] = relationship()
