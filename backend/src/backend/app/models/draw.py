"""Draw entity: one official draw of a lottery (CD-02, CD-04, CD-05)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.dataset_draw import DatasetDraw
    from backend.app.models.draw_number import DrawNumber
    from backend.app.models.lottery import Lottery
    from backend.app.models.super_number import SuperNumber


class Draw(Base):
    """A single official draw with its raw result columns (CD-02/CD-04).

    Raw-only storage: no derived values are persisted (CD-04). Rows are
    soft-deleted via ``is_deleted``; children ride FK RESTRICT (CD-05).
    No performance indexes are declared here — they belong to migration 0002
    (user rule: FK columns are intentionally NOT indexed in 0001).
    """

    __tablename__ = "draw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    draw_number: Mapped[int] = mapped_column(Integer, nullable=False)
    draw_date: Mapped[date] = mapped_column(Date, nullable=False)
    jackpot: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    winners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship(back_populates="draws")
    numbers: Mapped[list[DrawNumber]] = relationship(back_populates="draw")
    super_number: Mapped[SuperNumber | None] = relationship(back_populates="draw")
    dataset_draws: Mapped[list[DatasetDraw]] = relationship(back_populates="draw")

    __table_args__ = (
        # Natural key for idempotent F2 re-imports (design, Req 4).
        UniqueConstraint("lottery_id", "draw_number", name="uq_draw_lottery_draw_number"),
    )
