"""ExpRun entity: run association linking experiments to engine snapshots (EXP-003).

Polymorphic reference via (engine_type, engine_snapshot_id) — no DB FK.
Service validates that the referenced snapshot exists in the correct engine table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.exp_experiment import ExpExperiment

# Valid engine types (design, EXP-003): polymorphic reference.
EXP_ENGINE_TYPES = ("backtesting", "ml", "dl", "optimization")


class ExpRun(Base):
    """One run within an experiment, referencing an engine snapshot.

    The ``engine_snapshot_id`` references different tables based on
    ``engine_type``. No DB FK — service validates (design Snapshot Reference
    Pattern).
    """

    __tablename__ = "exp_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("exp_experiments.id", ondelete="RESTRICT"), nullable=False
    )
    run_label: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_type: Mapped[str] = mapped_column(String(20), nullable=False)
    engine_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    engine_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    experiment: Mapped[ExpExperiment] = relationship()

    __table_args__ = (
        CheckConstraint(
            "engine_type IN ('backtesting', 'ml', 'dl', 'optimization')",
            name="ck_exp_runs_engine_type",
        ),
    )
