"""Pydantic schemas for the ``draw`` resource (CD-02/CD-05; P4-01).

The read schema serializes the already-loaded ORM graph: the repository
eager-loads ``numbers`` and ``super_number`` (PR-2/PR-3 guarantee), so the API
never lazy-loads inside loops (design, scope item 8). ``super_number`` is the
nested 0..1 ``SuperNumber`` value exposed as a flat optional integer.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class DrawNumberRead(BaseModel):
    """One raw drawn number at its 1-based position (CD-02)."""

    model_config = ConfigDict(from_attributes=True)

    position: int
    number: int


class DrawRead(BaseModel):
    """Response body for a draw: raw columns plus nested numbers/super (CD-04)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lottery_id: int
    draw_number: int
    draw_date: date
    jackpot: Decimal | None
    winners: int | None
    is_deleted: bool
    created_at: datetime
    numbers: list[DrawNumberRead]
    super_number: int | None

    @field_validator("super_number", mode="before")
    @classmethod
    def _flatten_super_number(cls, value):
        """Extract ``value`` from the nested ORM ``SuperNumber`` (or keep ``None``)."""
        if value is None:
            return None
        return getattr(value, "value", value)
