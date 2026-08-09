"""MlMetric entity: one normalized ML metric payload row (design Data Model, M-A7/MLE-01).

Mirrors the ``stat_*``/``feature_*``/``prob_*``/``graph_*`` payload pattern: a
surrogate ``id`` PK (prob_* precedent) with an FK RESTRICT to the ``ml_snapshots``
header. ``value`` is an exact ``Decimal`` (Numeric(20,8)) — float NEVER reaches a
persisted value (float red line, MLE-05/D4). ``metric_name`` is one of the canonical
metrics (accuracy|precision|recall|f1|roc_auc, M-A7); ``params_json`` stores the
frozen, per-model hyperparameters as portable JSON Text — NEVER serialized weights
(joblib/pickle), which are out of the data model by contract (MLE-01).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.ml_snapshot import MlSnapshot


class MlMetric(Base):
    """One exact, Decimal-quantized metric for one model family on one target number.

    ``model_id`` mirrors the registry slug (e.g. 'rf'), ``model_version`` the
    registry/engine version identity, ``number`` the per-number target (MLE-03).
    The UNIQUE(snapshot_id, model_id, number, metric_name) cell keeps at most one
    value per metric per number per model (design Data Model).
    """

    __tablename__ = "ml_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("ml_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped[MlSnapshot] = relationship()

    __table_args__ = (
        # One value per (snapshot, model, number, metric_name) cell — MLE-01.
        UniqueConstraint(
            "snapshot_id",
            "model_id",
            "number",
            "metric_name",
            name="uq_ml_metrics_cell",
        ),
    )
