"""DlMetric entity: one normalized DL metric payload row (design Data Model, D-A7/DLE-01).

Mirrors the ``MlMetric`` pattern: a surrogate ``id`` PK with an FK RESTRICT to the
``dl_snapshots`` header. ``value`` is an exact ``Decimal`` (Numeric(20,8)) — float
NEVER reaches a persisted value (float red line, DLE-08). ``metric_name`` is one of
the canonical metrics (accuracy|precision|recall|f1|roc_auc, D-A7); ``params_json``
stores the frozen, per-model hyperparameters as portable JSON Text — including
architecture config (hidden layers, hidden size, etc.) and training params (epochs,
batch_size, lr).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.dl_snapshot import DlSnapshot


class DlMetric(Base):
    """One exact, Decimal-quantized metric for one model family on one target number.

    ``model_id`` mirrors the registry slug (e.g. 'mlp', 'lstm'), ``model_version`` the
    registry/engine version identity, ``number`` the per-number target (DLE-03).
    The UNIQUE(snapshot_id, model_id, number, metric_name) cell keeps at most one
    value per metric per number per model (design Data Model).
    """

    __tablename__ = "dl_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("dl_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped[DlSnapshot] = relationship()

    __table_args__ = (
        # One value per (snapshot, model, number, metric_name) cell — DLE-01.
        UniqueConstraint(
            "snapshot_id",
            "model_id",
            "number",
            "metric_name",
            name="uq_dl_metrics_cell",
        ),
    )
