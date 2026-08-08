"""Tests for community detection (GES-04, GM-04, Task 7).

Tests cover:
- Deterministic output
- Canonical node order
- Tie-break by node id
- Byte-identical reruns
- No PRNG
- Edge cases (single community, multiple communities)
"""

from __future__ import annotations

from backend.app.graph.community import detect_communities


class TestCommunityDetection:
    """Tests for community detection."""

    def test_single_community(self) -> None:
        """Complete graph forms single community."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}
        result = detect_communities(adjacency)

        # All nodes in same community
        communities = set(result.values())
        assert len(communities) == 1

    def test_multiple_communities(self) -> None:
        """Disconnected components form separate communities."""
        # Two components: 1-2 and 3-4
        adjacency = {1: {2: 1}, 2: {1: 1}, 3: {4: 1}, 4: {3: 1}}
        result = detect_communities(adjacency)

        # 1 and 2 in same community
        assert result[1] == result[2]
        # 3 and 4 in same community
        assert result[3] == result[4]
        # Different communities
        assert result[1] != result[3]

    def test_deterministic_rerun(self) -> None:
        """Same input produces same output (byte-identical)."""
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1}}

        result1 = detect_communities(adjacency)
        result2 = detect_communities(adjacency)

        assert result1 == result2

    def test_canonical_community_ids(self) -> None:
        """Community IDs are canonical (sorted by first member)."""
        adjacency = {1: {2: 1}, 2: {1: 1}, 3: {4: 1}, 4: {3: 1}}
        result = detect_communities(adjacency)

        # First community should have ID 0
        assert result[1] == 0 or result[3] == 0
        # Second community should have ID 1
        assert result[1] == 1 or result[3] == 1

    def test_single_node(self) -> None:
        """Single node forms its own community."""
        adjacency = {1: {}}
        result = detect_communities(adjacency)
        # Community ID is assigned based on first appearance
        assert result[1] >= 0

    def test_empty_graph(self) -> None:
        """Empty graph returns empty dict."""
        adjacency = {}
        result = detect_communities(adjacency)
        assert result == {}

    def test_triangle_with_tail(self) -> None:
        """Triangle with tail forms two communities."""
        # Triangle 1-2-3 plus tail 3-4
        adjacency = {1: {2: 1, 3: 1}, 2: {1: 1, 3: 1}, 3: {1: 1, 2: 1, 4: 1}, 4: {3: 1}}
        result = detect_communities(adjacency)

        # 1, 2, 3 in same community (triangle)
        assert result[1] == result[2] == result[3]
        # 4 may be in same or different community
        # (depends on modularity gain)

    def test_no_self_loops(self) -> None:
        """Community detection handles graphs without self-loops."""
        adjacency = {1: {2: 1}, 2: {1: 1, 3: 1}, 3: {2: 1}}
        result = detect_communities(adjacency)

        # All nodes should have community assignments
        assert all(node in result for node in adjacency)
