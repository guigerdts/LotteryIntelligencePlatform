"""Graph construction (GES-02, GM-02): adjacency graph from co-occurrence matrix.

Builds an adjacency graph from the co-occurrence matrix with threshold filtering.
Canonical node order, no self-loops, deterministic construction (REQ-02, D8).

Algorithm (GES-02):
- Nodes: lottery numbers from co-occurrence matrix
- Edges: co-occurrence >= threshold
- Edge weight: co-occurrence count
- Canonical node order: sorted by number
- No self-loops

Constraints:
- Graph is undirected (symmetric adjacency)
- No self-loops
- Deterministic construction
"""

from __future__ import annotations


def build_adjacency(
    cooccurrence: dict[tuple[int, int], int],
    threshold: int = 1,
) -> dict[int, dict[int, int]]:
    """Build adjacency graph from co-occurrence matrix.

    Args:
        cooccurrence: Dict of {(i, j): count} where i < j.
        threshold: Minimum co-occurrence count to include edge (default: 1).

    Returns:
        Adjacency dict: {node: {neighbor: weight}} with full symmetry.
        Nodes are sorted (canonical order).
    """
    adjacency: dict[int, dict[int, int]] = {}

    for (i, j), weight in cooccurrence.items():
        if weight >= threshold:
            if i not in adjacency:
                adjacency[i] = {}
            if j not in adjacency:
                adjacency[j] = {}
            adjacency[i][j] = weight
            adjacency[j][i] = weight

    return adjacency


def get_nodes(adjacency: dict[int, dict[int, int]]) -> list[int]:
    """Return sorted list of nodes (canonical order).

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        Sorted list of node IDs.
    """
    return sorted(adjacency.keys())


def get_edges(adjacency: dict[int, dict[int, int]]) -> list[tuple[int, int, int]]:
    """Return list of edges as (source, target, weight).

    Each edge appears once (source < target).

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        List of (source, target, weight) tuples.
    """
    edges: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()

    for source in sorted(adjacency.keys()):
        for target, weight in sorted(adjacency[source].items()):
            pair = (min(source, target), max(source, target))
            if pair not in seen:
                edges.append((pair[0], pair[1], weight))
                seen.add(pair)

    return edges
