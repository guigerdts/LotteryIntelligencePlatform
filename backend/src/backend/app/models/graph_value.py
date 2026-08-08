"""GraphValue entity: one normalized graph payload row (design Data Model, REQ-07/GES-06).

Mirrors the ``stat_*``/``feature_*``/``prob_*`` payload pattern with one deliberate
deviation: a surrogate ``id`` PK (D-A4) because ``draw_number`` is nullable — grid rows
(per-subject aggregates) have no draw axis, so a composite PK keyed on ``draw_number``
is impossible. ``draw_number`` is the official series axis and is a logical identifier
— there is NO physical FK to ``draw`` (stat_*/feature_*/prob_* parity); joins use
``draw_number`` only. The UNIQUE(snapshot_id, metric_type, subject, draw_number) keeps
at most one value per cell while permitting NULL draw rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.graph_snapshot import GraphSnapshot


class GraphValue(Base):
    """One exact graph metric value on the ``draw_number`` axis (or a grid row).

    ``value`` is an exact ``Decimal`` (Numeric(20,8)) from pure int/Decimal/Fraction
    math — float never reaches a persisted value (float red line, REQ-03). ``metric_type``
    is the canonical metric id (e.g. 'cooccurrence', 'centrality_degree', 'community_id',
    'density', 'modularity'), ``subject`` is the metric identity (e.g. a node pair,
    node id, or community label). ``params_json`` stores the frozen model params as
    portable JSON Text (dataset ``filters`` precedent, REQ-09); ``draw_number`` is NULL
    for non-draw grid rows (D-A4).
    """

    __tablename__ = "graph_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("graph_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    draw_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped[GraphSnapshot] = relationship()

    __table_args__ = (
        # One value per (snapshot, metric_type, subject, draw_number) cell — REQ-07.
        UniqueConstraint(
            "snapshot_id",
            "metric_type",
            "subject",
            "draw_number",
            name="uq_graph_values_cell",
        ),
    )
