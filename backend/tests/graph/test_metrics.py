"""Tests for network metrics (GES-05, GM-05, Task 8).

Tests cover:
- Density computation
- Modularity score
- Method registry
- Edge cases (empty, single node)
"""

from __future__ import annotations

from fractions import Fraction

from backend.app.graph.metrics import (
    compute_density,
    compute_modularity,
    compute_network_metrics,
    get_method_name,
    list_methods,
)


class TestDensity:
    """Tests for density computation."""

    def test_basic_density(self) -> None:
        """Basic density computation."""
        # Triangle: 3 nodes, 3 edges
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}
        result = compute_density(adjacency)

        # Max edges = 3*2/2 = 3
        # Density = 3/3 = 1
        assert result == Fraction(1)

    def test_path_graph(self) -> None:
        """Path graph density."""
        # Path: 1-2-3 (2 edges)
        adjacency = {1: {2: 1}, 2: {1: 1, 3: 1}, 3: {2: 1}}
        result = compute_density(adjacency)

        # Max edges = 3*2/2 = 3
        # Density = 2/3
        assert result == Fraction(2, 3)

    def test_single_node(self) -> None:
        """Single node has density 0."""
        adjacency = {1: {}}
        result = compute_density(adjacency)
        assert result == Fraction(0)

    def test_empty_graph(self) -> None:
        """Empty graph has density 0."""
        adjacency = {}
        result = compute_density(adjacency)
        assert result == Fraction(0)

    def test_complete_graph(self) -> None:
        """Complete graph has density 1."""
        adjacency = {1: {2: 1, 3: 1, 4: 1}, 2: {1: 1, 3: 1, 4: 1},
                     3: {1: 1, 2: 1, 4: 1}, 4: {1: 1, 2: 1, 3: 1}}
        result = compute_density(adjacency)
        assert result == Fraction(1)


class TestModularity:
    """Tests for modularity score."""

    def test_single_community(self) -> None:
        """Single community has modularity 0."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}
        communities = {1: 0, 2: 0, 3: 0}
        result = compute_modularity(adjacency, communities)

        assert result == Fraction(0)

    def test_perfect_communities(self) -> None:
        """Two disconnected components have modularity ~1."""
        adjacency = {1: {2: 1}, 2: {1: 1}, 3: {4: 1}, 4: {3: 1}}
        communities = {1: 0, 2: 0, 3: 1, 4: 1}
        result = compute_modularity(adjacency, communities)

        # Perfect community structure
        assert result > Fraction(0)

    def test_empty_graph(self) -> None:
        """Empty graph has modularity 0."""
        adjacency = {}
        communities = {}
        result = compute_modularity(adjacency, communities)
        assert result == Fraction(0)


class TestNetworkMetrics:
    """Tests for network metrics computation."""

    def test_basic_metrics(self) -> None:
        """Basic metrics computation."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}
        communities = {1: 0, 2: 0, 3: 0}
        result = compute_network_metrics(adjacency, communities)

        assert result.node_count == 3
        assert result.edge_count == 3
        assert result.density == Fraction(1)
        assert result.modularity == Fraction(0)


class TestMethodRegistry:
    """Tests for method registry."""

    def test_get_method_name(self) -> None:
        """Get method name from registry."""
        assert get_method_name("GM-01") == "cooccurrence"
        assert get_method_name("GM-02") == "construction"
        assert get_method_name("GM-03") == "centrality"
        assert get_method_name("GM-04") == "communities"
        assert get_method_name("GM-05") == "metrics"

    def test_unknown_method(self) -> None:
        """Unknown method raises KeyError."""
        try:
            get_method_name("GM-99")
            raise AssertionError("Should have raised KeyError")
        except KeyError as e:
            assert "Unknown method" in str(e)

    def test_list_methods(self) -> None:
        """List all methods."""
        methods = list_methods()
        assert len(methods) == 5
        assert "GM-01" in methods
        assert "GM-05" in methods
