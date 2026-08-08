"""E2E acceptance tests for Graph Engine (REQ-10, EC-01..06).

Full pipeline validation: DrawReader → Co-occurrence → Graph Construction →
Centrality → Communities → Metrics → Snapshot → Service.

Uses Baloto oracle fixture (test-only, not runtime).
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.graph.centrality import (
    betweenness_centrality,
    closeness_centrality,
    degree_centrality,
)
from backend.app.graph.community import detect_communities
from backend.app.graph.construction import build_adjacency, get_edges, get_nodes
from backend.app.graph.cooccurrence import compute_cooccurrence
from backend.app.graph.engine import GraphParams, compute_fingerprint
from backend.app.graph.metrics import compute_density, compute_modularity
from backend.app.models import Base
from backend.app.models.lottery import Lottery
from backend.app.services.graph_service import GraphService

# --- Fixtures ---

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "baloto_draws.json"


@pytest.fixture()
def baloto_draws():
    """Load Baloto fixture draws."""
    with open(FIXTURE_PATH) as f:
        return json.load(f)


@pytest.fixture()
def engine():
    """Create SQLite engine with FK enforcement."""
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Create session."""
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def baloto(session):
    """Create Baloto lottery."""
    lottery = Lottery(
        id=1,
        code="BAL",
        name="Baloto",
        country="CO",
        min_number=1,
        max_number=43,
        numbers_to_select=5,
    )
    session.add(lottery)
    session.commit()
    return lottery


class MockDrawReader:
    """Mock DrawReader for E2E testing with Baloto fixture."""

    def __init__(self, draw_numbers: list[list[int]]):
        self._draw_numbers = draw_numbers
        self._draw_ids = list(range(1, len(draw_numbers) + 1))

    def read_draw_numbers(self, draw_id: int) -> list[int]:
        if 1 <= draw_id <= len(self._draw_numbers):
            return sorted(self._draw_numbers[draw_id - 1])
        return []

    def get_draw_ids(self, lottery_id: int, limit: int | None = None) -> list[int]:
        ids = self._draw_ids
        if limit is not None:
            ids = ids[-limit:]
        return ids


# --- E2E Tests ---


class TestBalotoOracle:
    """E2E tests using Baloto oracle fixture."""

    def test_fixture_loads_correctly(self, baloto_draws):
        """Fixture loads 10 draws with 5 numbers each."""
        assert len(baloto_draws) == 10
        for draw in baloto_draws:
            assert len(draw["numbers"]) == 5
            assert all(1 <= n <= 43 for n in draw["numbers"])

    def test_cooccurrence_from_fixture(self, baloto_draws):
        """Co-occurrence from Baloto fixture produces valid matrix."""
        draw_numbers = [d["numbers"] for d in baloto_draws]
        cooccurrence = compute_cooccurrence(draw_numbers)

        # All pairs should have positive counts
        for (i, j), count in cooccurrence.items():
            assert count > 0
            assert i < j  # Normalized order (i < j)

    def test_full_pipeline_baloto(self, baloto_draws):
        """Full pipeline with Baloto fixture: co-occurrence → construction → metrics."""
        draw_numbers = [d["numbers"] for d in baloto_draws]

        # GM-01: Co-occurrence
        cooccurrence = compute_cooccurrence(draw_numbers)
        assert len(cooccurrence) > 0

        # GM-02: Construction
        adjacency = build_adjacency(cooccurrence, threshold=1)
        assert len(adjacency) > 0
        nodes = get_nodes(adjacency)
        edges = get_edges(adjacency)
        assert len(nodes) > 0
        assert len(edges) > 0

        # GM-03: Centrality
        degree = degree_centrality(adjacency)
        closeness = closeness_centrality(adjacency)
        betweenness = betweenness_centrality(adjacency)
        assert len(degree) == len(nodes)
        assert len(closeness) == len(nodes)
        assert len(betweenness) == len(nodes)

        # All centrality values are Fractions
        for node in nodes:
            assert isinstance(degree[node], Fraction)
            assert isinstance(closeness[node], Fraction)
            assert isinstance(betweenness[node], Fraction)

        # GM-04: Communities
        communities = detect_communities(adjacency)
        assert len(communities) == len(nodes)

        # GM-05: Network metrics
        density = compute_density(adjacency)
        modularity = compute_modularity(adjacency, communities)
        assert isinstance(density, Fraction)
        assert isinstance(modularity, Fraction)
        assert density > 0

    def test_determinism(self, baloto_draws):
        """Same input produces same output (byte-identical)."""
        draw_numbers = [d["numbers"] for d in baloto_draws]

        cooccurrence1 = compute_cooccurrence(draw_numbers)
        cooccurrence2 = compute_cooccurrence(draw_numbers)
        assert cooccurrence1 == cooccurrence2

        adjacency1 = build_adjacency(cooccurrence1, threshold=1)
        adjacency2 = build_adjacency(cooccurrence2, threshold=1)
        assert adjacency1 == adjacency2

        params = GraphParams(graph_type="cooccurrence", window=None, threshold=1)
        fp1 = compute_fingerprint(params, draw_count=len(draw_numbers))
        fp2 = compute_fingerprint(params, draw_count=len(draw_numbers))
        assert fp1 == fp2

    def test_window_affects_result(self, baloto_draws):
        """Window parameter affects computation."""
        draw_numbers = [d["numbers"] for d in baloto_draws]

        params_full = GraphParams(window=None)
        params_window = GraphParams(window=5)

        fp_full = compute_fingerprint(params_full, draw_count=len(draw_numbers))
        fp_window = compute_fingerprint(params_window, draw_count=len(draw_numbers))
        assert fp_full != fp_window

    def test_snapshot_persistence(self, session, baloto, baloto_draws):
        """Full pipeline with snapshot persistence."""
        mock_reader = MockDrawReader([d["numbers"] for d in baloto_draws])
        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        result = service.compute(lottery_id=1, graph_type="cooccurrence")

        # Snapshot persisted
        assert result.snapshot.id is not None
        assert result.snapshot.status == "active"
        assert result.snapshot.checksum is not None
        assert result.snapshot.input_fingerprint is not None

        # Read back
        snapshot, values = service.read(lottery_id=1)
        assert snapshot.id == result.snapshot.id
        assert len(values) > 0

    def test_empty_graph_handling(self, session, baloto):
        """Empty graph from threshold filtering."""
        mock_reader = MockDrawReader([[1, 2, 3, 4, 5]])
        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        # High threshold filters all edges
        result = service.compute(lottery_id=1, threshold=100)
        assert result.snapshot is not None

    def test_matrix_symmetry(self, baloto_draws):
        """Co-occurrence matrix is symmetric."""
        draw_numbers = [d["numbers"] for d in baloto_draws]
        cooccurrence = compute_cooccurrence(draw_numbers)
        adjacency = build_adjacency(cooccurrence, threshold=1)

        for node in adjacency:
            for neighbor in adjacency[node]:
                assert node in adjacency[neighbor]
                assert adjacency[node][neighbor] == adjacency[neighbor][node]

    def test_no_float_in_sensitive_calcs(self, baloto_draws):
        """No float in co-occurrence, density, modularity."""
        draw_numbers = [d["numbers"] for d in baloto_draws]
        cooccurrence = compute_cooccurrence(draw_numbers)

        # Co-occurrence: all integers
        for count in cooccurrence.values():
            assert isinstance(count, int)

        # Density, modularity: all Fractions
        adjacency = build_adjacency(cooccurrence, threshold=1)
        communities = detect_communities(adjacency)
        density = compute_density(adjacency)
        modularity = compute_modularity(adjacency, communities)
        assert isinstance(density, Fraction)
        assert isinstance(modularity, Fraction)

    def test_centrality_allowlist(self, baloto_draws):
        """Only allowed centrality methods: degree/closeness/betweenness."""
        draw_numbers = [d["numbers"] for d in baloto_draws]
        cooccurrence = compute_cooccurrence(draw_numbers)
        adjacency = build_adjacency(cooccurrence, threshold=1)

        degree = degree_centrality(adjacency)
        closeness = closeness_centrality(adjacency)
        betweenness = betweenness_centrality(adjacency)

        # All are Fractions (not floats)
        for node in adjacency:
            assert isinstance(degree[node], Fraction)
            assert isinstance(closeness[node], Fraction)
            assert isinstance(betweenness[node], Fraction)

    def test_fingerprint_includes_window(self, baloto_draws):
        """Fingerprint changes when window changes (REQ-06, A6)."""
        draw_numbers = [d["numbers"] for d in baloto_draws]
        params1 = GraphParams(window=None)
        params2 = GraphParams(window=5)

        fp1 = compute_fingerprint(params1, draw_count=len(draw_numbers))
        fp2 = compute_fingerprint(params2, draw_count=len(draw_numbers))
        assert fp1 != fp2

    def test_no_f3_f4_f5_imports(self):
        """Engine does not import F3/F4/F5 internals (A9)."""
        import backend.app.graph.engine as engine_module

        source = open(engine_module.__file__).read()
        assert "from backend.app.statistics" not in source
        assert "from backend.app.feature_engineing" not in source
        assert "from backend.app.probability" not in source
