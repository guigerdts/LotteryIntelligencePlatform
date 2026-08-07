"""Pydantic schemas for the statistics surface (design §5, backend delta).

Ships three groups: the ``GenerateRequest`` body for ``POST /statistics/generate``,
the snapshot header returned on generation (and echoed on reads), and the on-demand
read payloads for ``GET /statistics/{code}/...`` (frequencies/gaps/averages).
Reads are purely served from an existing snapshot — this schema group never
triggers precompute (STE-10/C5); the API only forwards the read request to the
service, which raises ``SnapshotNotFoundError`` when no snapshot exists.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Scope = Annotated[
    Literal["incremental", "full"],
    Field(description="incremental folds the delta; full rebuilds from scratch"),
]

# The single supported metric bundle for this release (generator.CORE_METRICS).
METRIC_SETS: frozenset[str] = frozenset({"core"})


class GenerateRequest(BaseModel):
    """Payload for ``POST /statistics/generate`` (unknown fields rejected).

    ``lottery_code`` identifies the lottery by natural key; ``metrics`` selects a
    supported metric bundle (default ``["core"]``); ``scope`` defaults to
    ``incremental`` (design §5). The endpoint is idempotent: a request that would
    reproduce the active snapshot exactly returns it instead of a new version.
    """

    model_config = ConfigDict(extra="forbid")

    lottery_code: str = Field(min_length=1, max_length=32)
    metrics: list[str] = Field(default_factory=lambda: ["core"])
    scope: Literal["incremental", "full"] = "incremental"


class GenerateSnapshot(BaseModel):
    """Snapshot header echoed on generation (design §5 response ``data``)."""

    snapshot_id: int
    lottery_code: str
    version: str
    metric_set: str
    generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    incremental: bool


class FrequencyRow(BaseModel):
    """One ``(number, count)`` of the overall frequency distribution."""

    number: int
    count: int


class FrequencyList(BaseModel):
    """Frequencies read: snapshot header + bounded list of frequency rows."""

    snapshot_id: int
    lottery_code: str
    version: str
    generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    frequencies: list[FrequencyRow]


class GapRow(BaseModel):
    """One per-number gap summary (avg_gap is NULL when no gap observed, D4)."""

    number: int
    count: int
    min_gap: int | None
    max_gap: int | None
    avg_gap: float | None


class GapList(BaseModel):
    """Gaps read the snapshot header + a bounded list of gap summaries."""

    snapshot_id: int
    lottery_code: str
    version: str
    generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    gaps: list[GapRow]


class AverageRow(BaseModel):
    """One NULL-aware series mean (non_null_count; mean may be None, D4)."""

    mean: float | None
    non_null_count: int


class AverageList(BaseModel):
    """Averages read the snapshot header + the jackpot/winners series means."""

    snapshot_id: int
    lottery_code: str
    version: str
    generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    averages: dict[str, AverageRow]  # series_key -> {mean, non_null_count}
