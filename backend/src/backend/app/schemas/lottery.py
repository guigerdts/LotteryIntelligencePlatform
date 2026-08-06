"""Pydantic schemas for the ``lottery`` resource (CD-01; P4-01).

Request validation lives at the API boundary: Pydantic field types enforce the
HTTP contract (ISO 3166-1 alpha-2 ``country`` length, string bounds, integer
rule columns). Cross-field invariants (``min_number < max_number``,
``numbers_to_select`` vs the range) are owned by the DB CHECK constraints and
the service layer (CD-06) — the API never re-implements business rules beyond
field-level types (design, scope item 4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LotteryCreate(BaseModel):
    """Payload for ``POST /lotteries``: the full lottery rule set (CD-01)."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=2, max_length=2)
    description: str | None = None
    min_number: int
    max_number: int
    numbers_to_select: int
    super_number_min: int | None = None
    super_number_max: int | None = None


class LotteryUpdate(BaseModel):
    """Payload for ``PUT /lotteries/{id}``: update of mutable fields.

    ``code`` is updatable (the design's transaction table rolls back a UNIQUE
    ``code`` conflict on PUT, surfacing DUPLICATE_RESOURCE 409). Unknown fields
    are rejected (``extra="forbid"``) so the API boundary never silently drops
    client data.
    """

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    description: str | None = None
    min_number: int | None = None
    max_number: int | None = None
    numbers_to_select: int | None = None
    super_number_min: int | None = None
    super_number_max: int | None = None


class LotteryRead(BaseModel):
    """Response body for a lottery row (from ORM attributes)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    country: str
    description: str | None
    min_number: int
    max_number: int
    numbers_to_select: int
    super_number_min: int | None
    super_number_max: int | None
    created_at: datetime
