"""Network metrics (GES-05, GM-05): density, modularity score, registry.

Implements graph-level network metrics and method registry. All metrics
use Fraction for exact arithmetic (REQ-05, D8).

Metrics:
- Density: |E| / (V * (V-1) / 2)
- Modularity: Newman modularity score of community assignment

Registry:
- GM-01: co-occurrence
- GM-02: construction
- GM-03: centrality
- GM-04: communities
- GM-05: metrics

Constraints:
- All metrics are Decimal (no float)
- Deterministic output
"""

from __future__ import annotations

from fractions import Fraction
from typing import NamedTuple

from backend.app.graph.construction import get_edges, get_nodes


class NetworkMetricsResult(NamedTuple):
    """Network metrics result.

    Attributes:
        density: Graph density.
        modularity: Newman modularity score.
        node_count: Number of nodes.
        edge_count: Number of edges.
    """

    density: Fraction
    modularity: Fraction
    node_count: int
    edge_count: int


def compute_density(adjacency: dict[int, dict[int, int]]) -> Fraction:
    """Compute graph density.

    Density: |E| / (V * (V-1) / 2)

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        Density as Fraction.
    """
    nodes = get_nodes(adjacency)
    v = len(nodes)
    if v <= 1:
        return Fraction(0)

    edges = get_edges(adjacency)
    e = len(edges)

    max_edges = Fraction(v * (v - 1), 2)
    return Fraction(e, max_edges)


def compute_modularity(
    adjacency: dict[int, dict[int, int]],
    communities: dict[int, int],
) -> Fraction:
    """Compute Newman modularity score.

    Modularity: Q = (1/2m) * Σ_{ij} [A_{ij} - (k_i * k_j) / 2m] * δ(c_i, c_j)

    where:
    - A_{ij} is adjacency matrix
    - k_i is degree of node i
    - m is total edge weight
    - δ(c_i, c_j) is 1 if nodes i,j are in same community

    Args:
        adjacency: Adjacency dict from build_adjacency.
        communities: Community assignment {node: community_id}.

    Returns:
        Modularity score as Fraction.
    """
    nodes = get_nodes(adjacency)
    if not nodes:
        return Fraction(0)

    # Total edge weight (sum of all edge weights, counted once)
    total_weight = sum(
        weight for source, target, weight in get_edges(adjacency)
    )
    if total_weight == 0:
        return Fraction(0)

    m2 = Fraction(total_weight * 2)

    # Compute modularity
    q = Fraction(0)

    for node_i in nodes:
        for node_j in nodes:
            # Adjacency value (0 if no edge)
            a_ij = adjacency.get(node_i, {}).get(node_j, 0)

            # Degrees
            k_i = sum(adjacency.get(node_i, {}).values())
            k_j = sum(adjacency.get(node_j, {}).values())

            # Delta (1 if same community)
            delta = 1 if communities.get(node_i) == communities.get(node_j) else 0

            q += Fraction(a_ij) - Fraction(k_i * k_j, m2)
            q *= delta

    return Fraction(1, 2 * total_weight) * q


def compute_network_metrics(
    adjacency: dict[int, dict[int, int]],
    communities: dict[int, int],
) -> NetworkMetricsResult:
    """Compute all network metrics.

    Args:
        adjacency: Adjacency dict from build_adjacency.
        communities: Community assignment {node: community_id}.

    Returns:
        NetworkMetricsResult with all metrics.
    """
    density = compute_density(adjacency)
    modularity = compute_modularity(adjacency, communities)
    nodes = get_nodes(adjacency)
    edges = get_edges(adjacency)

    return NetworkMetricsResult(
        density=density,
        modularity=modularity,
        node_count=len(nodes),
        edge_count=len(edges),
    )


# Method registry (GM-01..GM-05)
METHOD_REGISTRY: dict[str, str] = {
    "GM-01": "cooccurrence",
    "GM-02": "construction",
    "GM-03": "centrality",
    "GM-04": "communities",
    "GM-05": "metrics",
}


def get_method_name(method_id: str) -> str:
    """Get method name from registry.

    Args:
        method_id: Method ID (e.g. 'GM-01').

    Returns:
        Method name.

    Raises:
        KeyError: If method_id not in registry.
    """
    if method_id not in METHOD_REGISTRY:
        raise KeyError(f"Unknown method: {method_id}")
    return METHOD_REGISTRY[method_id]


def list_methods() -> dict[str, str]:
    """List all registered methods.

    Returns:
        Dict of {method_id: method_name}.
    """
    return dict(METHOD_REGISTRY)
