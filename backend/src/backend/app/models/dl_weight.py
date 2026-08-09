"""DlWeight entity: one serialized DL model weights BLOB (design Data Model, DLE-09).

Stores the custom-format weights binary (magic + format_version + fingerprint +
tensor manifest + raw float32 LE + SHA-256) as a BLOB. Maximum size 16 MiB enforced
by CHECK constraint and validated at write time. ``weights_fingerprint`` links the
blob to the snapshot's ``input_fingerprint`` so tampered/mismatched weights are
rejected on load. ``format_version`` enables forward-compatible decoding.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.dl_snapshot import DlSnapshot

# 16 MiB = 16 * 1024 * 1024 = 16_777_216 bytes.
_MAX_WEIGHTS_SIZE = 16_777_216


class DlWeight(Base):
    """One serialized DL model weights blob for one (snapshot, model_id) pair.

    ``weights_blob`` holds the custom-format binary; ``weights_size_bytes`` records
    the declared size for quick rejection without deserialization. ``weights_fingerprint``
    is the run fingerprint embedded in the blob header, enabling integrity validation
    without loading the full tensor data. ``format_version`` is the custom format
    version (currently 1) for forward-compatible decoding.
    """

    __tablename__ = "dl_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("dl_snapshots.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    weights_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    weights_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    weights_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    format_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    snapshot: Mapped[DlSnapshot] = relationship()

    __table_args__ = (
        CheckConstraint(
            f"weights_size_bytes <= {_MAX_WEIGHTS_SIZE}",
            name="ck_dl_weights_max_size",
        ),
    )
