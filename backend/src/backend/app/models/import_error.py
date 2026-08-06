"""ImportError entity: one per-row Phase B semantic failure (IE-03, design §4).

Rows rejected by Phase B are recorded verbatim (``raw_row``) with the typed
taxonomy ``error_code`` (design §7) so a run can be audited and reproduced. The
FK RESTRICT ties each failure to exactly one import run; structural-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.import_job import ImportJob


class ImportError(Base):
    """One Phase B row rejection: code, message, verbatim raw row (IE-03)."""

    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("imports.id", ondelete="RESTRICT"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    draw_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    error_code: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_row: Mapped[str] = mapped_column(Text, nullable=False)

    import_job: Mapped[ImportJob] = relationship(back_populates="errors")
