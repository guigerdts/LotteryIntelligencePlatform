"""Tests for graph_service module.

Covers GraphService computation, persistence, and error handling.
- Full pipeline: co-occurrence → construction → centrality/community/metrics
- Snapshot persistence
- Error handling

Ref: Task 11 (PR5), REQ-08, REQ-09, D7, A9.
"""

from fractions import Fraction

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base
from backend.app.models.lottery import Lottery
from backend.app.services.errors import NotFoundError, SnapshotNotFoundError, ValidationError
from backend.app.services.graph_service import GraphService

# --- Fixtures ---


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


# --- Mock DrawReader for testing ---


class MockDrawReader:
    """Mock DrawReader that returns fixed draw data."""

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


# --- Tests ---


class TestGraphServiceCompute:
    """Test GraphService.compute()."""

    def test_compute_full_pipeline(self, session, baloto):
        """Full pipeline: co-occurrence → construction → centrality/community/metrics."""
        # Mock the reader to return test data
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6],
            [3, 4, 5, 6, 7],
            [4, 5, 6, 7, 8],
            [5, 6, 7, 8, 9],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        result = service.compute(
            lottery_id=1,
            graph_type="cooccurrence",
            window=None,
            threshold=1,
        )

        # Verify result structure
        assert result.snapshot is not None
        assert result.adjacency is not None
        assert isinstance(result.density, Fraction)
        assert isinstance(result.modularity, Fraction)

        # Verify snapshot persisted
        assert result.snapshot.lottery_id == 1
        assert result.snapshot.graph_type == "cooccurrence"
        assert result.snapshot.status == "active"

    def test_compute_with_window(self, session, baloto):
        """Compute with rolling window."""
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6],
            [3, 4, 5, 6, 7],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        result = service.compute(
            lottery_id=1,
            graph_type="cooccurrence",
            window=2,
            threshold=1,
        )

        assert result.snapshot is not None

    def test_compute_lottery_not_found(self, session):
        """Raise NotFoundError for non-existent lottery."""
        mock_reader = MockDrawReader([])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        with pytest.raises(NotFoundError):
            service.compute(lottery_id=999)

    def test_compute_no_draws(self, session, baloto):
        """Raise ValidationError for empty draws."""
        mock_reader = MockDrawReader([])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        with pytest.raises(ValidationError):
            service.compute(lottery_id=1)


class TestGraphServiceRead:
    """Test GraphService.read()."""

    def test_read_active_snapshot(self, session, baloto):
        """Read active snapshot after compute."""
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        # Compute first
        result = service.compute(lottery_id=1)

        # Read active
        snapshot, values = service.read(
            lottery_id=1,
            graph_type="cooccurrence",
        )

        assert snapshot.id == result.snapshot.id
        assert len(values) > 0

    def test_read_by_fingerprint(self, session, baloto):
        """Read snapshot by fingerprint."""
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        # Compute first
        result = service.compute(lottery_id=1)
        fp = result.snapshot.input_fingerprint

        # Read by fingerprint
        snapshot, values = service.read(
            lottery_id=1,
            graph_type="cooccurrence",
            fingerprint=fp,
        )

        assert snapshot.input_fingerprint == fp
        assert len(values) > 0

    def test_read_not_found(self, session, baloto):
        """Raise SnapshotNotFoundError when no snapshot exists."""
        mock_reader = MockDrawReader([])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        with pytest.raises(SnapshotNotFoundError):
            service.read(lottery_id=1)


class TestGraphServiceIntegration:
    """Integration tests: verify full pipeline with real components."""

    def test_full_pipeline_real_components(self, session, baloto):
        """Full pipeline with real co-occurrence, construction, centrality, etc."""
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6],
            [3, 4, 5, 6, 7],
            [4, 5, 6, 7, 8],
            [5, 6, 7, 8, 9],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        result = service.compute(lottery_id=1)

        # Verify co-occurrence
        assert len(result.adjacency) > 0

        # Verify density
        assert isinstance(result.density, Fraction)

        # Verify modularity
        assert isinstance(result.modularity, Fraction)

        # Verify snapshot has all required fields
        assert result.snapshot.checksum is not None
        assert result.snapshot.input_fingerprint is not None
        assert result.snapshot.params_json is not None

    def test_empty_snapshot_persistence(self, session, baloto):
        """Verify empty snapshot handling."""
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        result = service.compute(lottery_id=1, threshold=100)

        # Should persist empty snapshot
        assert result.snapshot is not None
        assert result.snapshot.status == "active"

    def test_upsert_retires_old(self, session, baloto):
        """Verify upsert retires old snapshot."""
        mock_reader = MockDrawReader([
            [1, 2, 3, 4, 5],
            [2, 3, 4, 5, 6],
        ])

        service = GraphService.__new__(GraphService)
        service._session = session
        service._reader = mock_reader

        # First compute
        result1 = service.compute(lottery_id=1)
        id1 = result1.snapshot.id

        # Second compute
        result2 = service.compute(lottery_id=1)
        id2 = result2.snapshot.id

        # IDs should be different
        assert id1 != id2

        # First should be retired
        from sqlalchemy import select

        from backend.app.models.graph_snapshot import GraphSnapshot

        stmt = select(GraphSnapshot).where(GraphSnapshot.id == id1)
        old = session.scalar(stmt)
        assert old.status == "retired"
