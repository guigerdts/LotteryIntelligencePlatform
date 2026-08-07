"""FeatureValue entity: one normalized feature payload row (design §2, FES-01/FES-03).

Mirrors the ``stat_*`` payload pattern: a per-(feature, draw_number) exact ``Decimal``
value. ``draw_number`` is the official series axis and is a logical identifier — there is
NO physical FK to ``draw`` (FES-03, stat_* parity); joins use ``draw_number`` only. The
composite PK ``(snapshot_id, feature_id, draw_number)`` keeps one feature value per draw.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.feature_snapshot import FeatureSnapshot


class FeatureValue(Base):
    """One exact feature value on the ``draw_number`` axis.

    ``value`` is an exact ``Decimal`` (Numeric(20,8)) from a deterministic fold — float
    never reaches a persisted value (FES-05). ``feature_version`` is that feature's own
    version (design §6 approval Q1), bumped only when its algorithm/params change.
    """

    __tablename__ = "feature_values"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("feature_snapshots.id", ondelete="RESTRICT"), primary_key=True
    )
    feature_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False)
    draw_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    snapshot: Mapped[FeatureSnapshot] = relationship()
