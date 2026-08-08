"""Graph Engine: orchestrates GM-01..GM-05 with deterministic fingerprint.

The engine computes co-occurrence, builds adjacency, and orchestrates
centrality/community/metrics. Fingerprint includes window param (REQ-06, A6).

Algorithm:
1. Read draws via DrawReader
2. Compute co-occurrence (GM-01)
3. Build adjacency (GM-02)
4. Return adjacency for downstream (centrality/community/metrics)

Constraints:
- Deterministic output (byte-identical reruns)
- Fingerprint includes all params
- DrawReader only (A9, no F3/F4/F5 imports)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from backend.app.graph.construction import build_adjacency
from backend.app.graph.cooccurrence import compute_cooccurrence


class DrawReader(Protocol):
    """Protocol for reading draws from the database.

    Mirrors the F3/F5 DrawReader pattern (A9): the graph engine reads
    draws only through this protocol, never importing F3/F4/F5 internals.
    """

    def read_draw_numbers(self, draw_id: int) -> list[int]:
        """Return sorted list of main numbers for a draw (no super_number)."""
        ...

    def get_draw_ids(self, lottery_id: int, limit: int | None = None) -> list[int]:
        """Return draw IDs in chronological order for a lottery."""
        ...


@dataclass(frozen=True)
class GraphParams:
    """Immutable parameters for graph computation.

    Attributes:
        graph_type: Type of graph computation (e.g. 'cooccurrence').
        window: None for full-history, int for rolling window.
        threshold: Minimum co-occurrence count for edge.
        version: Engine version string.
    """

    graph_type: str = "cooccurrence"
    window: int | None = None
    threshold: int = 1
    version: str = "1.0.0"


def compute_fingerprint(params: GraphParams, draw_count: int) -> str:
    """Compute deterministic fingerprint for graph computation.

    The fingerprint uniquely identifies a graph computation based on:
    - All parameters (graph_type, window, threshold, version)
    - Number of draws (for change detection)

    Args:
        params: Graph computation parameters.
        draw_count: Number of draws used in computation.

    Returns:
        SHA-256 hex string (64 chars).
    """
    payload = json.dumps(
        {
            "graph_type": params.graph_type,
            "window": params.window,
            "threshold": params.threshold,
            "version": params.version,
            "draw_count": draw_count,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class GraphResult:
    """Result of graph computation.

    Attributes:
        params: Parameters used for computation.
        fingerprint: Deterministic fingerprint.
        adjacency: Adjacency dict (symmetric).
        draw_count: Number of draws used.
    """

    params: GraphParams
    fingerprint: str
    adjacency: dict[int, dict[int, int]]
    draw_count: int


def compute_graph(
    reader: DrawReader,
    lottery_id: int,
    params: GraphParams | None = None,
) -> GraphResult:
    """Compute graph from draws via DrawReader.

    This is the main entry point for graph computation. It reads draws
    through the DrawReader protocol (A9), computes co-occurrence (GM-01),
    builds adjacency (GM-02), and returns a GraphResult with fingerprint.

    Args:
        reader: DrawReader protocol instance.
        lottery_id: Lottery ID to compute for.
        params: Graph parameters (default: GraphParams()).

    Returns:
        GraphResult with adjacency and fingerprint.
    """
    if params is None:
        params = GraphParams()

    # Read draws via protocol (A9)
    draw_ids = reader.get_draw_ids(lottery_id)
    if params.window is not None:
        draw_ids = draw_ids[-params.window:]

    draw_numbers = [reader.read_draw_numbers(did) for did in draw_ids]

    # GM-01: Co-occurrence
    cooccurrence = compute_cooccurrence(draw_numbers, window=None)

    # GM-02: Adjacency
    adjacency = build_adjacency(cooccurrence, threshold=params.threshold)

    # Fingerprint (REQ-06)
    fingerprint = compute_fingerprint(params, draw_count=len(draw_numbers))

    return GraphResult(
        params=params,
        fingerprint=fingerprint,
        adjacency=adjacency,
        draw_count=len(draw_numbers),
    )
