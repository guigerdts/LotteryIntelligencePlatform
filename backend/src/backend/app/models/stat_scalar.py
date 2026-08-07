"""StatScalar entity: dataset-level distribution/trend scalars (design §2/§10)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.stat_snapshot import StatSnapshot


class StatScalar(Base):
    """One ``(name, value)`` scalar row (design §2/§10).

    Hosts non-joinable dataset-level scalars such as ``entropy``; ``value`` is an
    exact `Decimal` (Numeric(20,8)) from a deterministic fold, never float.
    """

    __tablename__ = "stat_scalars"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("stat_snapshots.id", ondelete="RESTRICT"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    snapshot: Mapped[StatSnapshot] = relationship()
