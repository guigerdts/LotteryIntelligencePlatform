"""Pydantic schemas for graph engine (REQ-08, Task 10).

Mirrors ``schemas/probability.py`` (F5 parity): a ``ComputeRequest`` body for
``POST /graph/compute``, the snapshot header echoed on computation and reads,
and the on-demand read models for ``GET /graph/{code}/metrics``.

Reads are purely served from an existing stored snapshot — this schema group
never triggers a precompute (REQ-08).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

GraphType = Annotated[
    Literal["cooccurrence", "centrality", "community", "network"],
    Field(description="Type of graph computation"),
]

# The single supported graph bundle for this release.
GRAPH_TYPES: frozenset[str] = frozenset({"cooccurrence", "centrality", "community", "network"})


class ComputeRequest(BaseModel):
    """Payload for ``POST /graph/compute`` (unknown fields rejected, REQ-08).

    ``lottery_code`` identifies the lottery by natural key; ``graph_type``
    determines which computation to run.
    """

    model_config = ConfigDict(extra="forbid")

    lottery_code: str = Field(min_length=1, max_length=32)
    graph_type: GraphType = "cooccurrence"
    window: int | None = None
    threshold: int = 1


class ComputeSnapshot(BaseModel):
    """Snapshot header echoed on computation (response ``data``).

    ``graph_generator_version`` is this engine's algorithm identity (D7);
    ``checksum`` is the canonical SHA-256 of the persisted graph content.
    """

    snapshot_id: int
    lottery_code: str
    version: str
    graph_type: str
    graph_generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    fingerprint: str


class GraphValueRow(BaseModel):
    """One persisted graph value (REQ-07).

    ``value`` is carried as its exact ``Decimal`` string (never float);
    ``subject`` identifies the metric subject (e.g. a node pair, node id);
    ``draw_number`` is nullable (NULL for grid rows, D-A4).
    """

    metric_type: str
    subject: str
    draw_number: int | None
    value: str


class GraphMetrics(BaseModel):
    """Graph metrics read: snapshot header + list of persisted rows.

    Only INTEGER/``Decimal`` values are persisted; rows come from the
    stored ``graph_values`` only — no precompute (REQ-08).
    """

    snapshot_id: int
    lottery_code: str
    version: str
    graph_type: str
    graph_generator_version: str
    draws_from: int
    draws_to: int
    draw_count: int
    checksum: str
    fingerprint: str
    values: list[GraphValueRow]


class GraphSnapshotInfo(BaseModel):
    """Snapshot header for listing (minimal info)."""

    snapshot_id: int
    lottery_code: str
    version: str
    graph_type: str
    status: str
    draw_count: int
    created_at: str


class GraphSnapshotList(BaseModel):
    """List of graph snapshots for a lottery (REQ-08)."""

    class SnapshotItem(BaseModel):
        snapshot_id: int
        version: str
        status: str
        draw_count: int
        checksum: str
        created_at: str | None = None

    snapshots: list[SnapshotItem]


class GraphValuesResponse(BaseModel):
    """Graph values read response (REQ-08, no precompute)."""

    class Row(BaseModel):
        metric_type: str
        subject: str
        draw_number: int | None = None
        value: float

    rows: list[Row]
    count: int
