"""Pydantic schemas for the AI assistant API (F15, A-12; A-09 compare contract)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AssistantResponse(BaseModel):
    """Assistant output: Spanish text + engine identity (A-02)."""

    text: str
    engine_version: str
    fingerprint: str


class SummarizeRequest(BaseModel):
    """Body for ``POST /assistant/summarize`` (A-09)."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: int = Field(gt=0)
    run_ids: list[int] | None = Field(default=None, min_length=2)


class AssistRequest(BaseModel):
    """Body for ``POST /assistant/assist``: free-text question over a lottery."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    lottery_code: str = Field(min_length=1, max_length=32)
