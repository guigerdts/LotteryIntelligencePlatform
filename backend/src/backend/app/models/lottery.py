"""Lottery entity: a lottery game and its persisted rule set (CD-01)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.draw import Draw
    from backend.app.models.import_job import ImportJob


class Lottery(Base):
    """A lottery game with its rule columns (CD-01).

    Structural-only: columns and constraints, no business logic or validation
    (layered per design — persistence/structural concerns live in the model).
    """

    __tablename__ = "lottery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_number: Mapped[int] = mapped_column(Integer, nullable=False)
    max_number: Mapped[int] = mapped_column(Integer, nullable=False)
    numbers_to_select: Mapped[int] = mapped_column(Integer, nullable=False)
    super_number_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    super_number_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    draws: Mapped[list[Draw]] = relationship(back_populates="lottery")
    import_jobs: Mapped[list[ImportJob]] = relationship(back_populates="lottery")

    __table_args__ = (
        UniqueConstraint("code", name="uq_lottery_code"),
        CheckConstraint("min_number < max_number", name="ck_lottery_min_max"),
        CheckConstraint(
            "numbers_to_select <= max_number - min_number + 1",
            name="ck_lottery_numbers_to_select",
        ),
        CheckConstraint(
            "super_number_min IS NULL OR super_number_max IS NULL"
            " OR super_number_min <= super_number_max",
            name="ck_lottery_super_range",
        ),
    )
