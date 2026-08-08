"""Pydantic schemas for the probability surface (design §5, PES-08).

Mirrors ``schemas/feature_engine.py`` (F4 parity): a ``GenerateRequest`` body for
``POST /probability/generate``, the snapshot header echoed on generation and reads,
and the on-demand read models for ``GET /probability/{code}/probabilities``.
Reads are purely served from an existing stored snapshot — this schema group never
triggers a precompute (PES-08).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Scope = Annotated[
    Literal["incremental", "full"],
    Field(description="incremental may recompute the needed set; full rebuilds from scratch"),
]

# The single supported model bundle for this release (service.PROB_MODEL_SET_CORE).
MODEL_SETS: frozenset[str] = frozenset({"core"})


class GenerateRequest(BaseModel):
    """Payload for ``POST /probability/generate`` (unknown fields rejected, PES-08).

    ``lottery_code`` identifies the lottery by natural key; ``scope`` defaults to
    ``incremental`` (design §7). The endpoint is idempotent: a request that would
    reproduce the active snapshot exactly returns it instead of a new version.
    """

    model_config = ConfigDict(extra="forbid")

    lottery_code: str = Field(min_length=1, max_length=32)
    model_set: str = "core"
    scope: Literal["incremental", "full"] = "incremental"


class GenerateSnapshot(BaseModel):
    """Snapshot header echoed on generation (design §2 response ``data``).

    ``prob_generator_version`` is this engine's algorithm identity, independent of
    ``STATS_GENERATOR_VERSION``/``FEATURE_GENERATOR_VERSION`` (PES-04); ``checksum``
    is the canonical SHA-256 of the persisted probability content (PES-05).
    """

    snapshot_id: int
    lottery_code: str
    version: str
    model_set: str
    prob_generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    incremental: bool


class ProbRow(BaseModel):
    """One persisted probability value (PES-01).

    ``value`` is carried as its exact ``Decimal`` string (never float — PES-05);
    ``subject`` identifies the probability bucket/quantile; ``draw_number`` is
    nullable (NULL for distribution-level rows, PES-03).
    """

    model_id: str
    model_version: str
    subject: str
    draw_number: int | None
    value: str


class ProbabilityList(BaseModel):
    """Probabilities read: snapshot header + a bounded list of persisted rows.

    Only INTEGER/``Decimal`` values are persisted (design §2); rows come from the
    stored ``prob_values`` only — no precompute (PES-08).
    """

    snapshot_id: int
    lottery_code: str
    version: str
    prob_generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    probabilities: list[ProbRow]
