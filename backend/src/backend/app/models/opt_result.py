"""OptResult entity: best found parameters + convergence for one optimization run (OE-13).

Mirrors the ``MlMetric``/``DlMetric`` payload pattern: a surrogate ``id`` PK with
an FK RESTRICT to the ``opt_snapshots`` header. ``best_fitness`` is stored as
``REAL`` (quantized to Decimal(20,8) in the application layer, OE-07); ``best_params``
holds the best found hyperparameters as portable JSON; ``convergence_history``
records the evaluation-by-evaluation fitness trajectory (OE-13).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.opt_snapshot import OptSnapshot


class OptResult(Base):
    """One best-found parameter set for one target model in an optimization run.

    ``target_model`` identifies the ML/DL family optimized (e.g. 'rf', 'mlp');
    ``best_params`` stores the winning hyperparameters as JSON; ``best_fitness``
    is the quantized objective metric value; ``convergence_history`` is a JSON
    list of {eval_num, fitness, timestamp} entries (OE-13).
    """

    __tablename__ = "opt_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("opt_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    target_model: Mapped[str] = mapped_column(String(64), nullable=False)
    best_params: Mapped[str] = mapped_column(Text, nullable=False)
    best_fitness: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    convergence_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    snapshot: Mapped[OptSnapshot] = relationship()
