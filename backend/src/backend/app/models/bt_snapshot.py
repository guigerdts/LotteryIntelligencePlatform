"""BtSnapshot entity: immutable header of one backtest run (design, BTE-01/10).

Header-only ORM mirroring ``OptSnapshot``/``MlSnapshot``/``DlSnapshot``: the
metrics payload lives in the sibling ``bt_results`` table FK'd to this row.
Immutability is enforced by the domain service (``status`` flip), never by
dialect triggers (REQ-09 portable). ``strategy_id`` scopes the run (BTE-03);
``config_json`` stores walk-forward configuration (BTE-04/18); ``fingerprint``
is the canonical SHA-256 invalidation key (BTE-06).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.repositories.base import Base

if TYPE_CHECKING:
    from backend.app.models.lottery import Lottery

# Lifecycle (design Snapshot Store & Service, BTE-10, mirroring prior snapshots):
# active = current, retired = superseded, failed = backtest that aborted.
# DB owns the domain via CHECK.
BT_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class BtSnapshot(Base):
    """One versioned, immutable backtest snapshot for a (lottery, strategy).

    Exactly one row has ``status='active'`` per ``(lottery_id, strategy_id)``
    -- enforced by the service in the same transaction that writes a new version
    (BTE-10). ``version`` is the human monotonic number; ``strategy_id`` is the
    strategy identity (e.g. 'ml-core-5', 'dl-core-3'); ``fingerprint`` is the
    canonical SHA-256 invalidation key (BTE-06).
    """

    __tablename__ = "bt_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        # One immutable version identity per (lottery, strategy) -- BTE-10.
        UniqueConstraint(
            "lottery_id",
            "strategy_id",
            "fingerprint",
            name="uq_bt_snapshots_scope_fingerprint",
        ),
        CheckConstraint("status IN ('active', 'retired', 'failed')", name="ck_bt_snapshots_status"),
    )
