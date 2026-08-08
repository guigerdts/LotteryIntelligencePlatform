"""Tests for graph engine (GES-06, Task 5).

Tests cover:
- DrawReader protocol
- Fingerprint computation
- Engine orchestration (GM-01, GM-02)
- Deterministic output
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.graph.engine import (
    GraphParams,
    GraphResult,
    compute_fingerprint,
    compute_graph,
)


@dataclass
class MockDrawReader:
    """Mock DrawReader for testing."""

    draws: list[list[int]]

    def read_draw_numbers(self, draw_id: int) -> list[int]:
        """Return sorted list of main numbers for a draw."""
        return sorted(self.draws[draw_id])

    def get_draw_ids(self, lottery_id: int, limit: int | None = None) -> list[int]:
        """Return draw IDs in chronological order."""
        ids = list(range(len(self.draws)))
        if limit is not None:
            ids = ids[-limit:]
        return ids


class TestFingerprint:
    """Tests for fingerprint computation."""

    def test_deterministic(self) -> None:
        """Same params produce same fingerprint."""
        params = GraphParams(graph_type="cooccurrence", window=None, threshold=1)
        fp1 = compute_fingerprint(params, draw_count=100)
        fp2 = compute_fingerprint(params, draw_count=100)

        assert fp1 == fp2

    def test_different_window(self) -> None:
        """Different window produces different fingerprint."""
        params1 = GraphParams(window=None)
        params2 = GraphParams(window=50)

        fp1 = compute_fingerprint(params1, draw_count=100)
        fp2 = compute_fingerprint(params2, draw_count=100)

        assert fp1 != fp2

    def test_different_threshold(self) -> None:
        """Different threshold produces different fingerprint."""
        params1 = GraphParams(threshold=1)
        params2 = GraphParams(threshold=2)

        fp1 = compute_fingerprint(params1, draw_count=100)
        fp2 = compute_fingerprint(params2, draw_count=100)

        assert fp1 != fp2

    def test_different_draw_count(self) -> None:
        """Different draw count produces different fingerprint."""
        params = GraphParams()

        fp1 = compute_fingerprint(params, draw_count=100)
        fp2 = compute_fingerprint(params, draw_count=200)

        assert fp1 != fp2

    def test_hex_format(self) -> None:
        """Fingerprint is 64-char hex string."""
        params = GraphParams()
        fp = compute_fingerprint(params, draw_count=100)

        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestGraphEngine:
    """Tests for graph engine orchestration."""

    def test_basic_computation(self) -> None:
        """Basic graph computation works."""
        reader = MockDrawReader(draws=[[1, 2, 3], [4, 5, 6]])
        result = compute_graph(reader, lottery_id=0)

        assert isinstance(result, GraphResult)
        assert result.draw_count == 2
        assert result.fingerprint is not None

    def test_adjacency_structure(self) -> None:
        """Adjacency has correct structure."""
        reader = MockDrawReader(draws=[[1, 2, 3]])
        result = compute_graph(reader, lottery_id=0)

        # All nodes should be in adjacency
        assert 1 in result.adjacency
        assert 2 in result.adjacency
        assert 3 in result.adjacency

        # Edges should exist
        assert 2 in result.adjacency[1]
        assert 3 in result.adjacency[1]
        assert 3 in result.adjacency[2]

    def test_deterministic_output(self) -> None:
        """Same input produces same output (byte-identical)."""
        reader = MockDrawReader(draws=[[1, 2, 3], [4, 5, 6]])

        result1 = compute_graph(reader, lottery_id=0)
        result2 = compute_graph(reader, lottery_id=0)

        assert result1.fingerprint == result2.fingerprint
        assert result1.adjacency == result2.adjacency

    def test_window_params(self) -> None:
        """Window parameter affects computation."""
        reader = MockDrawReader(draws=[[1, 2], [3, 4], [1, 3]])

        params_full = GraphParams(window=None)
        params_window = GraphParams(window=2)

        result_full = compute_graph(reader, lottery_id=0, params=params_full)
        result_window = compute_graph(reader, lottery_id=0, params=params_window)

        # Window=2 should only use last 2 draws
        assert result_full.draw_count == 3
        assert result_window.draw_count == 2

    def test_threshold_params(self) -> None:
        """Threshold parameter filters edges."""
        reader = MockDrawReader(draws=[[1, 2], [1, 2], [3, 4]])

        params_low = GraphParams(threshold=1)
        params_high = GraphParams(threshold=2)

        result_low = compute_graph(reader, lottery_id=0, params=params_low)
        result_high = compute_graph(reader, lottery_id=0, params=params_high)

        # (1,2) appears 2 times, (3,4) appears 1 time
        # threshold=2 should only include (1,2)
        assert 2 in result_low.adjacency[1]
        assert 4 in result_low.adjacency[3]

        assert 2 in result_high.adjacency[1]
        # (3,4) with count 1 should be excluded at threshold=2

    def test_empty_draws(self) -> None:
        """Empty draws produces empty graph."""
        reader = MockDrawReader(draws=[])
        result = compute_graph(reader, lottery_id=0)

        assert result.draw_count == 0
        assert result.adjacency == {}

    def test_single_draw(self) -> None:
        """Single draw produces complete graph."""
        reader = MockDrawReader(draws=[[1, 2, 3, 4, 5]])
        result = compute_graph(reader, lottery_id=0)

        assert result.draw_count == 1
        # C(5,2) = 10 edges
        total_edges = sum(len(neighbors) for neighbors in result.adjacency.values())
        assert total_edges == 20  # 10 edges * 2 directions

    def test_fingerprint_includes_window(self) -> None:
        """Fingerprint changes when window changes (REQ-06, A6)."""
        reader = MockDrawReader(draws=[[1, 2], [3, 4], [1, 3]])

        params1 = GraphParams(window=None)
        params2 = GraphParams(window=2)

        result1 = compute_graph(reader, lottery_id=0, params=params1)
        result2 = compute_graph(reader, lottery_id=0, params=params2)

        assert result1.fingerprint != result2.fingerprint

    def test_fingerprint_includes_threshold(self) -> None:
        """Fingerprint changes when threshold changes (REQ-06, A6)."""
        reader = MockDrawReader(draws=[[1, 2], [1, 2], [3, 4]])

        params1 = GraphParams(threshold=1)
        params2 = GraphParams(threshold=2)

        result1 = compute_graph(reader, lottery_id=0, params=params1)
        result2 = compute_graph(reader, lottery_id=0, params=params2)

        assert result1.fingerprint != result2.fingerprint

    def test_no_f3_f4_f5_imports(self) -> None:
        """Engine does not import F3/F4/F5 internals (A9)."""
        import backend.app.graph.engine as engine_module

        source = open(engine_module.__file__).read()
        assert "from backend.app.statistics" not in source
        assert "from backend.app.feature_engineering" not in source
        assert "from backend.app.probability" not in source
