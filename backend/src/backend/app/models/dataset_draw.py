"""DatasetDraw entity: association linking a dataset to a draw (CD-03 composition)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.dataset import Dataset
    from backend.app.models.draw import Draw


class DatasetDraw(Base):
    """A ``dataset_draws`` join row — one draw in one dataset composition (CD-03)."""

    __tablename__ = "dataset_draws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    draw_id: Mapped[int] = mapped_column(
        ForeignKey("draw.id", ondelete="RESTRICT"), nullable=False, index=False
    )

    dataset: Mapped[Dataset] = relationship(back_populates="dataset_draws")
    draw: Mapped[Draw] = relationship(back_populates="dataset_draws")

    __table_args__ = (UniqueConstraint("dataset_id", "draw_id", name="uq_dataset_draws_pair"),)
