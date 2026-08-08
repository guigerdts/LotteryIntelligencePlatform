"""ProbValue entity: one normalized probability payload row (design Data Model, PES-01/PES-03).

Mirrors the ``stat_*``/``feature_*`` payload pattern with one deliberate deviation: a
surrogate ``id`` PK (D-A4) because ``draw_number`` is nullable — grid rows (per-subject
aggregates and MC quantile rows) have no draw axis, so a composite PK keyed on
``draw_number`` is impossible (PES-03). ``draw_number`` is the official series axis and
is a logical identifier — there is NO physical FK to ``draw`` (PES-03, stat_*/feature_*
parity); joins use ``draw_number`` only. The UNIQUE(snapshot_id, model_id, model_version,
subject, draw_number) keeps at most one value per cell while permitting NULL draw rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.prob_snapshot import ProbSnapshot


class ProbValue(Base):
    """One exact probability value on the ``draw_number`` axis (or a grid row).

    ``value`` is an exact ``Decimal`` (Numeric(20,8)) from pure int/Decimal math —
    float never reaches a persisted value (PES-05). ``model_id`` is the canonical
    method id (registry), ``model_version`` that method's frozen version; ``subject``
    is the event identity (e.g. a number, or an MC quantile label). ``params_json``
    stores the frozen model params as portable JSON Text (dataset ``filters`` precedent,
    REQ-09); ``draw_number`` is NULL for non-draw grid rows (D-A4).
    """

    __tablename__ = "prob_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("prob_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    draw_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped[ProbSnapshot] = relationship()

    __table_args__ = (
        # One value per (snapshot, model, version, subject, draw_number) cell — PES-01.
        UniqueConstraint(
            "snapshot_id",
            "model_id",
            "model_version",
            "subject",
            "draw_number",
            name="uq_prob_values_cell",
        ),
    )
