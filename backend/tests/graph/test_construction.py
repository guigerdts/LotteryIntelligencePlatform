"""Tests for graph construction (GES-02, GM-02, Task 4).

Tests cover:
- Threshold semantics
- Canonical node order
- No self-loops
- Edge weight preservation
- Empty co-occurrence
"""

from __future__ import annotations

from backend.app.graph.construction import build_adjacency, get_edges, get_nodes


class TestConstruction:
    """Tests for graph construction."""

    def test_basic_construction(self) -> None:
        """Basic adjacency construction works."""
        cooccurrence = {(1, 2): 3, (2, 3): 1, (1, 3): 2}
        adjacency = build_adjacency(cooccurrence)

        # Check edges exist
        assert 1 in adjacency
        assert 2 in adjacency
        assert 3 in adjacency
        assert adjacency[1][2] == 3
        assert adjacency[2][1] == 3

    def test_threshold_filtering(self) -> None:
        """Edges below threshold are excluded."""
        cooccurrence = {(1, 2): 3, (2, 3): 1, (1, 3): 2}
        adjacency = build_adjacency(cooccurrence, threshold=2)

        # (2,3) with weight 1 is excluded
        assert 2 in adjacency
        assert 3 not in adjacency.get(2, {})
        # (1,2) with weight 3 is included
        assert adjacency[1][2] == 3

    def test_canonical_node_order(self) -> None:
        """Nodes are in sorted order."""
        cooccurrence = {(5, 10): 1, (1, 2): 1, (3, 4): 1}
        adjacency = build_adjacency(cooccurrence)
        nodes = get_nodes(adjacency)

        assert nodes == [1, 2, 3, 4, 5, 10]

    def test_no_self_loops(self) -> None:
        """No self-loops in adjacency."""
        cooccurrence = {(1, 2): 1, (2, 3): 1}
        adjacency = build_adjacency(cooccurrence)

        for node, neighbors in adjacency.items():
            assert node not in neighbors, f"Self-loop found at node {node}"

    def test_symmetry(self) -> None:
        """Adjacency is symmetric."""
        cooccurrence = {(1, 2): 3, (2, 3): 1}
        adjacency = build_adjacency(cooccurrence)

        assert adjacency[1][2] == adjacency[2][1]
        assert adjacency[2][3] == adjacency[3][2]

    def test_edge_weight_preservation(self) -> None:
        """Edge weights are preserved."""
        cooccurrence = {(1, 2): 5, (3, 4): 10}
        adjacency = build_adjacency(cooccurrence)

        assert adjacency[1][2] == 5
        assert adjacency[3][4] == 10

    def test_empty_cooccurrence(self) -> None:
        """Empty co-occurrence produces empty adjacency."""
        adjacency = build_adjacency({})
        assert adjacency == {}

    def test_get_nodes_empty(self) -> None:
        """get_nodes returns empty list for empty adjacency."""
        nodes = get_nodes({})
        assert nodes == []

    def test_get_edges_basic(self) -> None:
        """get_edges returns each edge once."""
        cooccurrence = {(1, 2): 3, (2, 3): 1, (1, 3): 2}
        adjacency = build_adjacency(cooccurrence)
        edges = get_edges(adjacency)

        # Each edge appears once
        assert len(edges) == 3
        # Check edge directions (source < target)
        for source, target, _weight in edges:
            assert source < target

    def test_get_edges_empty(self) -> None:
        """get_edges returns empty list for empty adjacency."""
        edges = get_edges({})
        assert edges == []

    def test_threshold_zero(self) -> None:
        """Threshold=0 includes all edges."""
        cooccurrence = {(1, 2): 0}
        adjacency = build_adjacency(cooccurrence, threshold=0)

        # Edge with weight 0 is included
        assert 1 in adjacency
        assert 2 in adjacency

    def test_threshold_high_excludes_all(self) -> None:
        """High threshold excludes all edges."""
        cooccurrence = {(1, 2): 1, (3, 4): 2}
        adjacency = build_adjacency(cooccurrence, threshold=10)

        assert adjacency == {}

    def test_get_edges_preserves_weight(self) -> None:
        """get_edges preserves edge weights."""
        cooccurrence = {(1, 2): 7, (3, 4): 3}
        adjacency = build_adjacency(cooccurrence)
        edges = get_edges(adjacency)

        weights = {(s, t): w for s, t, w in edges}
        assert weights[(1, 2)] == 7
        assert weights[(3, 4)] == 3
