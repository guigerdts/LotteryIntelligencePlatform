"""SuperNumber entity: the optional 0..1 super/star number per draw (CD-02, D2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.draw import Draw


class SuperNumber(Base):
    """The extra (super/star) number of a draw; at most one per draw (CD-02).

    The 0..1 cardinality is enforced by ``UNIQUE(draw_id)``; forward-compatible
    with multi-star lotteries by relaxing that constraint in a later migration
    (CD-08).
    """

    __tablename__ = "super_number"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draw_id: Mapped[int] = mapped_column(
        ForeignKey("draw.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)

    draw: Mapped[Draw] = relationship(back_populates="super_number")

    __table_args__ = (UniqueConstraint("draw_id", name="uq_super_number_draw_id"),)
