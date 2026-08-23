"""Pydantic v2 schemas for the Generator surface (GEN-010).

Request/response models for the four ``/gen`` endpoints. Mirrors the
``schemas/meta.py`` pattern: request bodies forbid unknown fields; responses
echo the snapshot header and, for generate/combinations, the stored rows.
The ``count`` range is validated by ``GenService`` (GEN-002 →
``GEN_COUNT_INVALID``), so the request schema keeps the field unconstrained.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Lifecycle statuses accepted by ``POST /gen/snapshot`` (GEN-007).
SnapshotStatus = Literal["active", "retired", "failed"]


class GenerateRequest(BaseModel):
    """Payload for ``POST /gen/generate`` (unknown fields rejected).

    ``lottery_id`` is required; ``count`` defaults to 10 (GEN-002), ``seed`` and
    ``selection_id`` are optional overrides (GEN-003, GEN-009).
    """

    model_config = ConfigDict(extra="forbid")

    lottery_id: int = Field(gt=0)
    count: int | None = None
    seed: int | None = None
    selection_id: int | None = Field(default=None, gt=0)


class CombinationRow(BaseModel):
    """One stored combination row (GEN-012).

    Tolerant read shape (D6/R2): ``super_number``/``score`` stay optional so
    legacy NULL-SB rows keep deserializing on reads.
    """

    model_config = ConfigDict(from_attributes=True)

    position: int
    numbers: list[int]
    super_number: int | None = None
    score: float | None = None


class GeneratedCombinationRow(CombinationRow):
    """One generated combination echoed by ``POST /gen/generate`` (R3).

    Strict echo typing: every freshly generated combination carries a NON-null
    Superbalota and finite selection-weighted score.
    """

    super_number: int
    score: float


class GenerationResult(BaseModel):
    """``POST /gen/generate`` response data — snapshot header plus combinations.

    Rows use the strict ``GeneratedCombinationRow`` (R3): the generate echo
    always carries non-null ``super_number``/``score``.
    """

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    lottery_id: int
    selection_id: int
    version: str
    status: str
    fingerprint: str
    seed: int
    count: int
    combinations: list[GeneratedCombinationRow]


class CombinationList(BaseModel):
    """``GET /gen/combinations`` response data."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    lottery_id: int
    combinations: list[CombinationRow]


class SnapshotUpdateRequest(BaseModel):
    """Payload for ``POST /gen/snapshot`` (unknown fields rejected).

    ``status`` is restricted to the lifecycle set (GEN-007); activating a
    snapshot is rejected by the service with ``GEN_DUPLICATE_SNAPSHOT``.
    """

    model_config = ConfigDict(extra="forbid")

    lottery_id: int = Field(gt=0)
    snapshot_id: int = Field(gt=0)
    status: SnapshotStatus


class SnapshotResult(BaseModel):
    """One stored generator snapshot header."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    lottery_id: int
    selection_id: int
    version: str
    status: str
    fingerprint: str
    created_at: str | None = None


class SnapshotList(BaseModel):
    """``GET /gen/snapshots`` response data."""

    model_config = ConfigDict(from_attributes=True)

    lottery_id: int
    snapshots: list[SnapshotResult]
