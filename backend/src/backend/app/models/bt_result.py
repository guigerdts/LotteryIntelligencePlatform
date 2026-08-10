"""BtResult entity: metrics and window history for one backtest run (BTE-08/15).

Mirrors the ``OptResult``/``MlMetric``/``DlMetric`` payload pattern: a surrogate
``id`` PK with an FK RESTRICT to the ``bt_snapshots`` header.
``aggregate_metrics_json`` stores the overall MetricSet as JSON (BTE-08);
``window_history_json`` stores per-window WindowResult list as JSON (BTE-15).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.bt_snapshot import BtSnapshot


class BtResult(Base):
    """Aggregate metrics and window history for one backtest run.

    ``aggregate_metrics_json`` holds the overall MetricSet as JSON;
    ``window_history_json`` holds the list of per-window WindowResult
    entries as JSON (BTE-15).
    """

    __tablename__ = "bt_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("bt_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    aggregate_metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    window_history_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    snapshot: Mapped[BtSnapshot] = relationship()
