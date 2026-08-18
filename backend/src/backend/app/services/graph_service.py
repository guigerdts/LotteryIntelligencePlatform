"""GraphService: orchestration, versioning, and atomic tx (REQ-07/D-A3).

Composition root for the Graph Engine slice. It owns:
- ``compute()`` — orchestration: resolve lottery, compute co-occurrence,
  build adjacency, run centrality/community/metrics, fingerprint + checksum,
  persist NEW version in ONE atomic tx. On error → terminal ``failed`` snapshot.
- ``read()`` — served from stored snapshot only, never precompute (REQ-08).

Reads draws ONLY via own DrawReader Protocol (A9); writes ONLY ``graph_*`` (REQ-07).
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from typing import NamedTuple

from sqlalchemy.orm import Session

from backend.app.core.response_cache import ThreadSafeLRU, register_cache
from backend.app.graph.centrality import (
    betweenness_centrality,
    closeness_centrality,
    degree_centrality,
)
from backend.app.graph.community import detect_communities
from backend.app.graph.construction import build_adjacency
from backend.app.graph.cooccurrence import compute_cooccurrence
from backend.app.graph.engine import GraphParams, compute_fingerprint
from backend.app.graph.metrics import compute_density, compute_modularity
from backend.app.graph.snapshot_store import (
    load_snapshot_by_fingerprint,
    load_snapshot_values,
    upsert_snapshot,
)
from backend.app.models.graph_snapshot import GraphSnapshot
from backend.app.services.errors import NotFoundError, SnapshotNotFoundError, ValidationError

# Supported graph types (D1).
GRAPH_TYPE_CORE: str = "cooccurrence"
GRAPH_TYPES: frozenset[str] = frozenset({"cooccurrence"})


class GraphResult(NamedTuple):
    """Result of graph computation.

    Attributes:
        snapshot: The persisted snapshot.
        adjacency: Adjacency dict (symmetric).
        density: Graph density.
        modularity: Modularity score.
    """

    snapshot: GraphSnapshot
    adjacency: dict[int, dict[int, int]]
    density: Fraction
    modularity: Fraction


class _DrawReaderAdapter:
    """Adapter wrapping draw repository into DrawReader Protocol (A9)."""

    def __init__(self, session: Session) -> None:
        from backend.app.repositories.draw_repository import DrawRepository

        self._repo = DrawRepository(session)

    def read_draw_numbers(self, draw_id: int) -> list[int]:
        """Return sorted list of main numbers for a draw."""
        from backend.app.models.draw_number import DrawNumber

        numbers = (
            self._repo._session.query(DrawNumber)
            .filter(DrawNumber.draw_id == draw_id)
            .order_by(DrawNumber.position)
            .all()
        )
        return sorted(n.number for n in numbers)

    def get_draw_ids(self, lottery_id: int, limit: int | None = None) -> list[int]:
        """Return draw IDs in chronological order for a lottery."""
        from backend.app.models.draw import Draw

        query = (
            self._repo._session.query(Draw.id)
            .filter(Draw.lottery_id == lottery_id)
            .order_by(Draw.draw_number)
        )
        if limit is not None:
            query = query.limit(limit)
        return [row[0] for row in query.all()]


_GRAPH_CACHE: ThreadSafeLRU[tuple, object] = ThreadSafeLRU(maxsize=256)
register_cache(_GRAPH_CACHE)


class GraphService:
    """Graph service: orchestration and snapshot lifecycle.

    Pattern mirrors StatisticsService/ProbabilityService (D-A3, A9).
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._reader = _DrawReaderAdapter(session)

    def compute(
        self,
        lottery_id: int,
        graph_type: str = "cooccurrence",
        window: int | None = None,
        threshold: int = 1,
    ) -> GraphResult:
        """Compute graph and persist snapshot.

        Args:
            lottery_id: Lottery ID.
            graph_type: Graph type (default: 'cooccurrence').
            window: Rolling window (None for full-history).
            threshold: Edge threshold.

        Returns:
            GraphResult with snapshot and metrics.

        Raises:
            NotFoundError: If lottery not found.
        """
        from backend.app.repositories.lottery_repository import LotteryRepository

        # Validate lottery exists
        lottery = LotteryRepository(self._session).get(lottery_id)
        if lottery is None:
            raise NotFoundError(f"lottery {lottery_id!r} not found")

        # Read draws
        draw_ids = self._reader.get_draw_ids(lottery_id)
        if not draw_ids:
            raise ValidationError("No draws found for lottery")

        if window is not None:
            draw_ids = draw_ids[-window:]

        draw_numbers = [self._reader.read_draw_numbers(did) for did in draw_ids]

        # GM-01: Co-occurrence
        cooccurrence = compute_cooccurrence(draw_numbers, window=None)

        # GM-02: Adjacency
        adjacency = build_adjacency(cooccurrence, threshold=threshold)

        # GM-03: Centrality
        degree = degree_centrality(adjacency)
        closeness = closeness_centrality(adjacency)
        betweenness = betweenness_centrality(adjacency)

        # GM-04: Communities
        communities = detect_communities(adjacency)

        # GM-05: Network metrics
        density = compute_density(adjacency)
        modularity = compute_modularity(adjacency, communities)

        # Compute fingerprint
        params = GraphParams(
            graph_type=graph_type,
            window=window,
            threshold=threshold,
        )
        fingerprint = compute_fingerprint(params, draw_count=len(draw_numbers))

        # Compute checksum
        checksum_payload = json.dumps(
            {
                "cooccurrence": {f"{k[0]}-{k[1]}": v for k, v in sorted(cooccurrence.items())},
                "density": str(density),
                "modularity": str(modularity),
            },
            sort_keys=True,
        )
        checksum = hashlib.sha256(checksum_payload.encode()).hexdigest()

        # Build values for persistence
        values: list[tuple[str, str, int | None, Decimal, str]] = []

        # Co-occurrence values
        for (i, j), count in sorted(cooccurrence.items()):
            values.append(("cooccurrence", f"{i}-{j}", None, Decimal(count), "{}"))

        # Centrality values
        for node in sorted(degree.keys()):
            values.append(
                ("centrality_degree", str(node), None, Decimal(float(degree[node])), "{}")
            )
            values.append(
                ("centrality_closeness", str(node), None, Decimal(float(closeness[node])), "{}")
            )
            values.append(
                ("centrality_betweenness", str(node), None, Decimal(float(betweenness[node])), "{}")
            )

        # Community values
        for node, comm_id in sorted(communities.items()):
            values.append(("community_id", str(node), None, Decimal(comm_id), "{}"))

        # Network metrics
        values.append(("density", "graph", None, density, "{}"))
        values.append(("modularity", "graph", None, modularity, "{}"))

        # Compute version: find existing max and increment
        from sqlalchemy import func, select

        stmt = select(func.max(GraphSnapshot.version)).where(
            GraphSnapshot.lottery_id == lottery_id,
            GraphSnapshot.graph_type == graph_type,
        )
        max_version: str | None = self._session.scalar(stmt)
        if max_version is not None:
            version = str(int(max_version) + 1)
        else:
            version = "1"

        # Persist snapshot (retires old active automatically)
        snapshot = upsert_snapshot(
            self._session,
            lottery_id=lottery_id,
            graph_type=graph_type,
            version=version,
            generator_version="1.0.0",
            checksum=checksum,
            fingerprint=fingerprint,
            params_json=json.dumps({"window": window, "threshold": threshold}),
            draw_count=len(draw_numbers),
            draws_from=min(draw_ids) if draw_ids else 0,
            draws_to=max(draw_ids) if draw_ids else 0,
            values=values,
        )

        return GraphResult(
            snapshot=snapshot,
            adjacency=adjacency,
            density=density,
            modularity=modularity,
        )

    def read(
        self,
        lottery_id: int,
        graph_type: str = "cooccurrence",
        fingerprint: str | None = None,
    ) -> tuple[GraphSnapshot, list[tuple[str, str, int | None, Decimal]]]:
        """Read graph from stored snapshot.

        Args:
            lottery_id: Lottery ID.
            graph_type: Graph type.
            fingerprint: Specific fingerprint (None for active).

        Returns:
            Tuple of (snapshot, list of (metric_type, subject, draw_number, value)).

        Raises:
            SnapshotNotFoundError: If snapshot not found.
        """
        if fingerprint is not None:
            snapshot = load_snapshot_by_fingerprint(
                self._session, lottery_id, graph_type, fingerprint
            )
        else:
            # Load active snapshot
            from sqlalchemy import select

            stmt = (
                select(GraphSnapshot)
                .where(
                    GraphSnapshot.lottery_id == lottery_id,
                    GraphSnapshot.graph_type == graph_type,
                    GraphSnapshot.status == "active",
                )
                .limit(1)
            )
            snapshot = self._session.scalar(stmt)

        if snapshot is None:
            raise SnapshotNotFoundError(
                f"No {graph_type} snapshot found for lottery {lottery_id!r}"
            )

        # Load values
        key = ("graph:read", snapshot.id, graph_type, fingerprint)
        cached = _GRAPH_CACHE.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        db_values = load_snapshot_values(self._session, snapshot.id)
        values = [(v.metric_type, v.subject, v.draw_number, v.value) for v in db_values]
        payload = (snapshot, values)
        _GRAPH_CACHE.set(key, payload)
        return payload
