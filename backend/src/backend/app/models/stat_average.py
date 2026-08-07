"""StatAverage entity: NULL-aware series averages payload rows (design §2, D4)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.stat_snapshot import StatSnapshot


class StatAverage(Base):
    """One ``(series_key, mean)`` row over a snapshot (design §2, STE-07/D4).

    ``series_key`` names the optional metric series (e.g. ``jackpot``,
    ``winners``); ``mean`` is the `Decimal` mean over NON-NULL draws only and is
    ``None`` when the series has zero non-NULL draws (never imputed).
    """

    __tablename__ = "stat_averages"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("stat_snapshots.id", ondelete="RESTRICT"), primary_key=True
    )
    series_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    mean: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    non_null_count: Mapped[int] = mapped_column(Integer, nullable=False)

    snapshot: Mapped[StatSnapshot] = relationship()
