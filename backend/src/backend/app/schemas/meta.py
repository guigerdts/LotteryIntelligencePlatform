"""Pydantic v2 schemas for Meta Learning API endpoints (META-013).

Request/response schemas for rank, ranking, select, selection endpoints.
Standard envelope {success, data|error, timestamp} wraps all responses.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# --- Request schemas ---


class RankRequest(BaseModel):
    """POST /meta/rank request body."""

    model_config = ConfigDict(extra="forbid")

    lottery_id: int = Field(gt=0)
    engine_types: list[str] | None = None
    weights: dict[str, float] | None = None


class SelectRequest(BaseModel):
    """POST /meta/select request body."""

    model_config = ConfigDict(extra="forbid")

    lottery_id: int = Field(gt=0)
    top_k: int | None = Field(default=None, gt=0, le=20)
    min_score: float | None = None


# --- Response schemas ---


class RankingEntryResponse(BaseModel):
    """Single entry within a ranking result."""

    model_config = ConfigDict(from_attributes=True)

    model_id: str
    engine_type: str
    score: float
    metrics: dict[str, float] = Field(default_factory=dict)


class RankingResult(BaseModel):
    """POST /meta/rank response data."""

    model_config = ConfigDict(from_attributes=True)

    ranking_id: int
    lottery_id: int
    context_hash: str
    version: str
    status: str
    fingerprint: str
    entries: list[RankingEntryResponse]


class RankingSnapshot(BaseModel):
    """GET /meta/ranking response data."""

    model_config = ConfigDict(from_attributes=True)

    lottery_id: int
    context_hash: str
    rankings: list[dict]


class SelectionEntryResponse(BaseModel):
    """Single entry within a selection result."""

    model_config = ConfigDict(from_attributes=True)

    model_id: str
    engine_type: str
    rank: int
    score: float


class SelectionResult(BaseModel):
    """POST /meta/select response data."""

    model_config = ConfigDict(from_attributes=True)

    selection_id: int
    lottery_id: int
    ranking_id: int
    context_hash: str
    version: str
    status: str
    fingerprint: str
    entries: list[SelectionEntryResponse]


class SelectionSnapshot(BaseModel):
    """GET /meta/selection response data."""

    model_config = ConfigDict(from_attributes=True)

    lottery_id: int
    context_hash: str
    selections: list[dict]
