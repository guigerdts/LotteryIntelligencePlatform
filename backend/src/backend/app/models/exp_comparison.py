"""ExpComparison entity: immutable cross-run comparison snapshot (EXP-005).

Stores the comparison matrix as JSON. Once persisted, never mutated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.exp_experiment import ExpExperiment


class ExpComparison(Base):
    """One comparison snapshot for an experiment.

    ``comparison_json`` holds the full comparison matrix. Once written,
    this row is never updated (immutability per NFR-EXP-04).
    """

    __tablename__ = "exp_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("exp_experiments.id", ondelete="RESTRICT"), nullable=False
    )
    run_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    comparison_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    experiment: Mapped[ExpExperiment] = relationship()
