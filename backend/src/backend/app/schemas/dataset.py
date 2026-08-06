"""Pydantic schemas for the ``dataset`` resource (CD-03; P4-01).

Created per PR-4 task P4-01 so the full schema surface exists; no Dataset CRUD
endpoints ship in Fase 1 (M4 — the ``/datasets`` contract is deferred, so no
router mounts these). The read model mirrors the immutability contract:
``is_locked`` is always exposed, ``checksum`` stays nullable until F2 computes
it (CD-03 reproducibility).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    """Payload for the (deferred) dataset creation endpoint."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=64)
    description: str | None = None
    lottery_id: int
    filters: str | None = None
    generator_version: str = Field(min_length=1, max_length=32)


class DatasetUpdate(BaseModel):
    """Metadata-only update; composition/filters changes require a new version (CD-03)."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None


class DatasetRead(BaseModel):
    """Response body for an immutable dataset row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    description: str | None
    lottery_id: int
    filters: str | None
    generator_version: str
    checksum: str | None
    is_locked: bool
    created_at: datetime
