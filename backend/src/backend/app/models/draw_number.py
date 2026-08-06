"""DrawNumber entity: one drawn number at a position within a draw (CD-02)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.draw import Draw


class DrawNumber(Base):
    """A raw drawn number at a given position (CD-02, raw-only per CD-04)."""

    __tablename__ = "draw_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draw_id: Mapped[int] = mapped_column(
        ForeignKey("draw.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    draw: Mapped[Draw] = relationship(back_populates="numbers")

    __table_args__ = (
        UniqueConstraint("draw_id", "position", name="uq_draw_numbers_draw_position"),
        UniqueConstraint("draw_id", "number", name="uq_draw_numbers_draw_number"),
    )
