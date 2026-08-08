"""Community detection (GES-04, GM-04): pure-greedy modularity.

Implements deterministic community detection via pure-greedy modularity
optimization. No PRNG, canonical node order, tie-break by node id (D3, REQ-04).

Algorithm:
1. Initialize: each node in its own community
2. For each edge (in canonical order):
   - Compute modularity gain for merging communities
   - If gain > 0, merge
3. Assign canonical community IDs (sorted by first member)

Constraints:
- Deterministic by construction
- Same input ⇒ same output (byte-identical)
- Complexity: O(VE)
"""

from __future__ import annotations

from fractions import Fraction

from backend.app.graph.construction import get_edges, get_nodes


def detect_communities(adjacency: dict[int, dict[int, int]]) -> dict[int, int]:
    """Detect communities via pure-greedy modularity.

    Args:
        adjacency: Adjacency dict from build_adjacency.

    Returns:
        Dict of {node: community_id} with canonical community IDs.
    """
    nodes = get_nodes(adjacency)
    if not nodes:
        return {}

    # Total edge weight (sum of all edge weights)
    total_weight = sum(
        weight for source, target, weight in get_edges(adjacency)
    )
    if total_weight == 0:
        # Each node is its own community
        return {n: n for n in nodes}

    # Initialize: each node in its own community
    community_of: dict[int, int] = {n: n for n in nodes}

    # Process edges in canonical order
    for source, target, weight in get_edges(adjacency):
        comm_source = community_of[source]
        comm_target = community_of[target]

        # Skip if already in same community
        if comm_source == comm_target:
            continue

        # Compute modularity gain for merging
        gain = _modularity_gain(
            adjacency, community_of, source, target, weight, total_weight
        )

        # Merge if gain > 0
        if gain > 0:
            # Merge target community into source community
            for node in nodes:
                if community_of[node] == comm_target:
                    community_of[node] = comm_source

    # Assign canonical community IDs (sorted by first member)
    return _canonical_community_ids(community_of, nodes)


def _modularity_gain(
    adjacency: dict[int, dict[int, int]],
    community_of: dict[int, int],
    node_i: int,
    node_j: int,
    weight_ij: int,
    total_weight: int,
) -> Fraction:
    """Compute modularity gain for merging two communities.

    This is the change in modularity if we merge the communities
    containing node_i and node_j.

    Args:
        adjacency: Adjacency dict.
        community_of: Current community assignment.
        node_i: First node.
        node_j: Second node.
        weight_ij: Weight of edge between node_i and node_j.
        total_weight: Total edge weight in graph.

    Returns:
        Modularity gain as Fraction (positive = beneficial).
    """
    if total_weight == 0:
        return Fraction(0)

    comm_i = community_of[node_i]
    comm_j = community_of[node_j]

    # Sum of degrees in each community
    sum_deg_i = _community_degree_sum(adjacency, community_of, comm_i)
    sum_deg_j = _community_degree_sum(adjacency, community_of, comm_j)

    # Edges between the two communities
    between_edges = weight_ij * 2  # Symmetric

    # Modularity gain formula
    m2 = Fraction(total_weight * 2)

    gain = Fraction(between_edges, m2) - (
        Fraction(sum_deg_i * sum_deg_j, m2 * m2)
    )

    return gain


def _community_degree_sum(
    adjacency: dict[int, dict[int, int]],
    community_of: dict[int, int],
    community: int,
) -> int:
    """Sum of degrees for all nodes in a community."""
    total = 0
    for node, comm in community_of.items():
        if comm == community:
            total += sum(adjacency.get(node, {}).values())
    return total


def _community_internal_edges(
    adjacency: dict[int, dict[int, int]],
    community_of: dict[int, int],
    community: int,
) -> int:
    """Count internal edges within a community."""
    count = 0
    for node, comm in community_of.items():
        if comm == community:
            for neighbor, weight in adjacency.get(node, {}).items():
                if community_of.get(neighbor) == community and node < neighbor:
                    count += weight
    return count


def _canonical_community_ids(
    community_of: dict[int, int],
    nodes: list[int],
) -> dict[int, int]:
    """Assign canonical community IDs (sorted by first member).

    Args:
        community_of: Current community assignment.
        nodes: Sorted list of all nodes.

    Returns:
        Dict of {node: canonical_community_id}.
    """
    # Map old community IDs to canonical IDs
    old_to_new: dict[int, int] = {}
    next_id = 0

    for node in nodes:
        old_comm = community_of[node]
        if old_comm not in old_to_new:
            old_to_new[old_comm] = next_id
            next_id += 1

    return {node: old_to_new[community_of[node]] for node in nodes}
