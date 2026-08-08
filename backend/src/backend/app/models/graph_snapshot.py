"""GraphSnapshot entity: immutable header of one graph snapshot (design Data Model, GES-06).

Header-only ORM mirroring ``StatSnapshot``/``FeatureSnapshot``/``ProbSnapshot``: the
normalized payload rows live in the sibling ``graph_values`` table FK'd to this row.
Immutability is enforced by the domain service (``is_locked`` guard + ``status`` flip),
never by dialect triggers (REQ-09 portable). ``graph_generator_version`` is independent
of ``STATS_GENERATOR_VERSION``, ``feature_engine_version``, and
``prob_generator_version`` (D7); ``input_fingerprint`` is the invalidation key
(design Seed/Determinism, REQ-06).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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


# Lifecycle (design Snapshot Store & Service, REQ-07, mirroring stat_*/feature_*/prob_*):
# active = current, retired = superseded, failed = generation that aborted, never
# active/partial. DB owns the domain via CHECK.
GRAPH_SNAPSHOT_STATUSES = ("active", "retired", "failed")


class GraphSnapshot(Base):
    """One versioned, immutable graph snapshot for a (lottery, graph_type).

    Exactly one row has ``status='active'`` per ``(lottery_id, graph_type)`` — enforced
    by the service in the same transaction that writes a new version (REQ-07). ``version``
    is the human monotonic number; ``graph_generator_version`` is this engine's algorithm
    identity (independent of Statistics/Feature/Probability, D7); ``checksum`` proves
    output determinism and ``input_fingerprint`` is the canonical SHA-256 invalidation
    key (REQ-06).
    """

    __tablename__ = "graph_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lottery_id: Mapped[int] = mapped_column(
        ForeignKey("lottery.id", ondelete="RESTRICT"), nullable=False, index=False
    )
    graph_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    graph_generator_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draw_count: Mapped[int] = mapped_column(Integer, nullable=False)
    draws_from: Mapped[int] = mapped_column(Integer, nullable=False)
    draws_to: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    lottery: Mapped[Lottery] = relationship()

    __table_args__ = (
        # One immutable version identity per (lottery, graph_type) — REQ-07.
        UniqueConstraint(
            "lottery_id", "graph_type", "version", name="uq_graph_snapshots_scope_version"
        ),
        CheckConstraint("draws_from <= draws_to", name="ck_graph_snapshots_range"),
        CheckConstraint(
            "status IN ('active', 'retired', 'failed')", name="ck_graph_snapshots_status"
        ),
    )
