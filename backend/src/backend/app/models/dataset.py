"""Dataset entity: immutable, versioned draw composition (CD-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.dataset_draw import DatasetDraw
    from backend.app.models.lottery import Lottery


class Dataset(Base):
    """An immutable dataset version with composition and reproducibility metadata (CD-03).

    Immutability is enforced by the domain service (``is_locked`` guard), not by
    the DB — DB triggers are dialect-specific and break REQ-09 portability.
    ``filters`` stores JSON as portable Text; ``checksum`` is computed in F2.
    """

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    filters: Mapped[str | None] = mapped_column(Text, nullable=True)
    generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lottery: Mapped[Lottery] = relationship()
    dataset_draws: Mapped[list[DatasetDraw]] = relationship(back_populates="dataset")

    __table_args__ = (UniqueConstraint("version", name="uq_datasets_version"),)
