"""Pydantic v2 schemas for the pipeline orchestrator surface (R3, D10).

One endpoint: ``POST /pipeline/numbers``. The request forbids unknown fields;
the response carries the ordered eight-stage report plus the generator output
(null on failure). Stage statuses are restricted to the R3 set.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.gen import GenerationResult


class PipelineRunRequest(BaseModel):
    """Payload for ``POST /pipeline/numbers`` (unknown fields rejected).

    ``lottery_id`` is required; ``count`` defaults backend-side to 10
    (GEN-002) and ``seed`` stays optional (GEN-003).
    """

    model_config = ConfigDict(extra="forbid")

    lottery_id: int = Field(gt=0)
    count: int | None = None
    seed: int | None = None


class PipelineStageResult(BaseModel):
    """One ordered stage entry of the per-stage report (R3)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    status: Literal["skipped", "completed", "failed"]
    snapshot_id: int | None = None
    fingerprint: str | None = None
    error_code: str | None = None
    detail: str = ""


class PipelineRunResult(BaseModel):
    """``POST /pipeline/numbers`` response data (R1/R3).

    ``stages`` lists exactly the eight canonical stages in order; ``result``
    is the generation echo or ``None`` when the run aborted.
    """

    model_config = ConfigDict(from_attributes=True)

    stages: list[PipelineStageResult]
    result: GenerationResult | None = None
