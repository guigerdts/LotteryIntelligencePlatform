"""Tests for centrality engine (GES-03, GM-03, Task 6).

Tests cover:
- Degree centrality
- Closeness centrality
- Betweenness centrality
- Decimal safety (Fraction-based)
- Edge cases (single node, disconnected)
"""

from __future__ import annotations

from fractions import Fraction

from backend.app.graph.centrality import (
    betweenness_centrality,
    closeness_centrality,
    degree_centrality,
)


class TestDegreeCentrality:
    """Tests for degree centrality."""

    def test_basic_degree(self) -> None:
        """Basic degree centrality computation."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1}, 3: {1: 1}}
        result = degree_centrality(adjacency)

        # Node 1: degree 2, V=3, centrality = 2/2 = 1
        assert result[1] == Fraction(1)
        # Node 2: degree 1, centrality = 1/2
        assert result[2] == Fraction(1, 2)
        # Node 3: degree 1, centrality = 1/2
        assert result[3] == Fraction(1, 2)

    def test_single_node(self) -> None:
        """Single node has degree centrality 0."""
        adjacency = {1: {}}
        result = degree_centrality(adjacency)
        assert result[1] == Fraction(0)

    def test_empty_graph(self) -> None:
        """Empty graph returns empty dict."""
        adjacency = {}
        result = degree_centrality(adjacency)
        assert result == {}

    def test_complete_graph(self) -> None:
        """Complete graph has degree centrality 1 for all nodes."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}
        result = degree_centrality(adjacency)

        for _node, score in result.items():
            assert score == Fraction(1)

    def test_isolated_node(self) -> None:
        """Isolated node has degree centrality 0."""
        adjacency = {1: {2: 1}, 2: {1: 1}, 3: {}}
        result = degree_centrality(adjacency)

        assert result[3] == Fraction(0)


class TestClosenessCentrality:
    """Tests for closeness centrality."""

    def test_basic_closeness(self) -> None:
        """Basic closeness centrality computation."""
        # Path graph: 1-2-3
        adjacency = {1: {2: 1}, 2: {1: 1, 3: 1}, 3: {2: 1}}
        result = closeness_centrality(adjacency)

        # Node 2: distances to others = {1: 1, 3: 1}, sum = 2
        # Closeness = (3-1) / 2 = 1
        assert result[2] == Fraction(1)

    def test_star_graph(self) -> None:
        """Star graph: center has highest closeness."""
        adjacency = {1: {2: 1, 3: 1, 4: 1}, 2: {1: 1}, 3: {1: 1}, 4: {1: 1}}
        result = closeness_centrality(adjacency)

        # Node 1: distances = {2: 1, 3: 1, 4: 1}, sum = 3
        # Closeness = 3/3 = 1
        assert result[1] == Fraction(1)

    def test_single_node(self) -> None:
        """Single node has closeness centrality 0."""
        adjacency = {1: {}}
        result = closeness_centrality(adjacency)
        assert result[1] == Fraction(0)

    def test_empty_graph(self) -> None:
        """Empty graph returns empty dict."""
        adjacency = {}
        result = closeness_centrality(adjacency)
        assert result == {}

    def test_disconnected_component(self) -> None:
        """Node in disconnected component has limited closeness."""
        # Two components: 1-2 and 3-4
        adjacency = {1: {2: 1}, 2: {1: 1}, 3: {4: 1}, 4: {3: 1}}
        result = closeness_centrality(adjacency)

        # Node 1: can reach node 2, but not 3 and 4
        # BFS returns distances to all nodes, but unreachable nodes have no distance
        # The algorithm sums distances to all nodes except self
        # Since 3 and 4 are unreachable, they're not in distances
        # So sum = distance to 2 = 1
        # Closeness = (4-1) / 1 = 3
        assert result[1] == Fraction(3)


class TestBetweennessCentrality:
    """Tests for betweenness centrality."""

    def test_basic_betweenness(self) -> None:
        """Basic betweenness centrality computation."""
        # Path graph: 1-2-3
        adjacency = {1: {2: 1}, 2: {1: 1, 3: 1}, 3: {2: 1}}
        result = betweenness_centrality(adjacency)

        # Node 2 is on all shortest paths between 1 and 3
        # For undirected graph, each pair counted once
        assert result[2] > Fraction(0)
        # Nodes 1 and 3 are endpoints
        assert result[1] == Fraction(0)
        assert result[3] == Fraction(0)

    def test_complete_graph(self) -> None:
        """Complete graph has betweenness 0 for all nodes."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}
        result = betweenness_centrality(adjacency)

        for score in result.values():
            assert score == Fraction(0)

    def test_single_node(self) -> None:
        """Single node has betweenness 0."""
        adjacency = {1: {}}
        result = betweenness_centrality(adjacency)
        assert result[1] == Fraction(0)

    def test_empty_graph(self) -> None:
        """Empty graph returns empty dict."""
        adjacency = {}
        result = betweenness_centrality(adjacency)
        assert result == {}

    def test_star_graph_center(self) -> None:
        """Star graph: center has high betweenness."""
        adjacency = {1: {2: 1, 3: 1, 4: 1}, 2: {1: 1}, 3: {1: 1}, 4: {1: 1}}
        result = betweenness_centrality(adjacency)

        # All paths between leaves go through center
        # There are C(3,2) = 3 pairs of leaves
        # Each pair has 1 shortest path through center
        assert result[1] > Fraction(0)
        # Leaves have 0 betweenness
        assert result[2] == Fraction(0)
        assert result[3] == Fraction(0)
        assert result[4] == Fraction(0)
