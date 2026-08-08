"""Centrality engine (GES-03, GM-03): degree, closeness, betweenness.

Implements three centrality metrics on the adjacency graph. All metrics
use Fraction for exact arithmetic, converting to Decimal once at the end
(REQ-03, D4, D8, A7).

Algorithms:
- Degree: count of neighbors / (V-1) — O(1)/node
- Closeness: (V-1) / sum(shortest paths) — O(V²)
- Betweenness: Brandes algorithm with int path counts — O(VE)

Constraints:
- All scores are Decimal (no float)
- Float red line enforced
- Deterministic output
"""

from __future__ import annotations

from collections import deque
from fractions import Fraction
from typing import NamedTuple

from backend.app.graph.construction import get_nodes


class CentralityScores(NamedTuple):
    """Centrality scores for all nodes.

    Attributes:
        degree: Degree centrality per node.
        closeness: Closeness centrality per node.
        betweenness: Betweenness centrality per node.
    """

    degree: dict[int, Fraction]
    closeness: dict[int, Fraction]
    betweenness: dict[int, Fraction]


def degree_centrality(adjacency: dict[int, dict[int, int]]) -> dict[int, Fraction]:
    """Compute degree centrality for each node.

    Degree centrality: d(v) = |neighbors(v)| / (V - 1)

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        Dict of {node: Fraction} with degree centrality scores.
    """
    nodes = get_nodes(adjacency)
    v = len(nodes)
    if v <= 1:
        return {n: Fraction(0) for n in nodes}

    result: dict[int, Fraction] = {}
    for node in nodes:
        degree = len(adjacency.get(node, {}))
        result[node] = Fraction(degree, v - 1)

    return result


def closeness_centrality(adjacency: dict[int, dict[int, int]]) -> dict[int, Fraction]:
    """Compute closeness centrality for each node.

    Closeness centrality: c(v) = (V-1) / sum(shortest paths from v)

    Uses BFS for unweighted shortest paths (O(V²)).

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        Dict of {node: Fraction} with closeness centrality scores.
    """
    nodes = get_nodes(adjacency)
    v = len(nodes)
    if v <= 1:
        return {n: Fraction(0) for n in nodes}

    result: dict[int, Fraction] = {}

    for source in nodes:
        # BFS from source
        distances = _bfs_distances(adjacency, source, nodes)
        total_distance = sum(distances.get(n, 0) for n in nodes if n != source)

        if total_distance == 0:
            result[source] = Fraction(0)
        else:
            result[source] = Fraction(v - 1, total_distance)

    return result


def _bfs_distances(
    adjacency: dict[int, dict[int, int]],
    source: int,
    nodes: list[int],
) -> dict[int, int]:
    """BFS to compute shortest distances from source.

    Args:
        adjacency: Adjacency dict.
        source: Starting node.
        nodes: List of all nodes.

    Returns:
        Dict of {node: distance} from source.
    """
    distances: dict[int, int] = {source: 0}
    queue: deque[int] = deque([source])

    while queue:
        current = queue.popleft()
        current_dist = distances[current]

        for neighbor in sorted(adjacency.get(current, {})):
            if neighbor not in distances:
                distances[neighbor] = current_dist + 1
                queue.append(neighbor)

    return distances


def betweenness_centrality(adjacency: dict[int, dict[int, int]]) -> dict[int, Fraction]:
    """Compute betweenness centrality using Brandes algorithm.

    Betweenness centrality: b(v) = Σ_{s≠v≠t} σ_st(v) / σ_st

    Uses integer path counts (no float) and Fraction for accumulation.

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        Dict of {node: Fraction} with betweenness centrality scores.
    """
    nodes = get_nodes(adjacency)
    v = len(nodes)
    if v <= 1:
        return {n: Fraction(0) for n in nodes}

    # Initialize betweenness to 0
    betweenness: dict[int, Fraction] = {n: Fraction(0) for n in nodes}

    for source in nodes:
        # Brandes BFS
        predecessors: dict[int, list[int]] = {n: [] for n in nodes}
        sigma: dict[int, int] = {n: 0 for n in nodes}
        sigma[source] = 1
        distances: dict[int, int] = {n: -1 for n in nodes}
        distances[source] = 0

        queue: deque[int] = deque([source])
        stack: list[int] = []

        while queue:
            current = queue.popleft()
            stack.append(current)

            for neighbor in sorted(adjacency.get(current, {})):
                # First time discovering neighbor
                if distances[neighbor] == -1:
                    distances[neighbor] = distances[current] + 1
                    queue.append(neighbor)

                # Shortest path to neighbor goes through current
                if distances[neighbor] == distances[current] + 1:
                    sigma[neighbor] += sigma[current]
                    predecessors[neighbor].append(current)

        # Back-propagation
        delta: dict[int, Fraction] = {n: Fraction(0) for n in nodes}

        while stack:
            w = stack.pop()
            for v_node in predecessors[w]:
                delta[v_node] += Fraction(sigma[v_node], sigma[w]) * (Fraction(1) + delta[w])

            if w != source:
                betweenness[w] += delta[w]

    return betweenness
