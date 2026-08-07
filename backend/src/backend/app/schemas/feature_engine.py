"""Pydantic schemas for the feature-engine surface (design §2/§5, backend delta).

Mirrors ``schemas/statistics.py`` (Fase 3 parity): a ``GenerateRequest`` body for
``POST /feature-engine/generate``, the snapshot header echoed on generation and on
reads, and the on-demand read models for ``GET /feature-engine/{code}/features``.
Reads are purely served from an existing stored snapshot — this schema group never
triggers a precompute (FES-09) and the API forwards the read to the service, which
raises ``SnapshotNotFoundError`` when no snapshot exists.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Scope = Annotated[
    Literal["incremental", "full"],
    Field(description="incremental may recompute the needed set; full rebuilds from scratch"),
]

# The single supported feature bundle for this release (service.FEATURE_SET_CORE).
FEATURE_SETS: frozenset[str] = frozenset({"core"})


class GenerateRequest(BaseModel):
    """Payload for ``POST /feature-engine/generate`` (unknown fields rejected, FES-09).

    ``lottery_code`` identifies the lottery by natural key; ``scope`` defaults to
    ``incremental`` (design §7). The endpoint is idempotent: a request that would
    reproduce the active snapshot exactly returns it instead of a new version.
    """

    model_config = ConfigDict(extra="forbid")

    lottery_code: str = Field(min_length=1, max_length=32)
    scope: Literal["incremental", "full"] = "incremental"


class GenerateSnapshot(BaseModel):
    """Snapshot header echoed on generation (design §2 response ``data``).

    ``feature_engine_version`` is this engine's algorithm identity, independent of
    ``STATS_GENERATOR_VERSION`` (FES-04); ``checksum`` is the canonical SHA-256 of
    the persisted feature-set content (FES-05).
    """

    snapshot_id: int
    lottery_code: str
    version: str
    feature_set: str
    feature_engine_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    incremental: bool


class FeatureRow(BaseModel):
    """One persisted scalar feature value on the ``draw_number`` axis (FES-03).

    ``value`` is carried as its exact ``Decimal`` string (never float — FES-05);
    the numeric cell itself is the canonical ``str(value)`` used by the checksum.
    """

    feature_id: str
    feature_version: str
    draw_number: int
    value: str


class FeatureList(BaseModel):
    """Features read: snapshot header + a bounded list of persisted feature rows.

    Only INTEGER/``Decimal`` scalar values are persisted (design §2); mapping features
    (FE-07 decade_distribution, FE-10 current_frequency) are computed and fingerprinted
    but carry no stored cell — so they never appear here, exactly as written (FES-05).
    """

    snapshot_id: int
    lottery_code: str
    version: str
    feature_engine_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    features: list[FeatureRow]
