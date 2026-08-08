"""Tests for ProbabilityService (PR2b, T-12).

Uses in-memory SQLite with real ORM; mock providers for deterministic control.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.prob_snapshot import ProbSnapshot
from backend.app.probability.providers import DrawRow, LotteryRules
from backend.app.probability.registry import build_prob_registry
from backend.app.probability.snapshot_store import SnapshotStore
from backend.app.repositories.base import Base
from backend.app.services.probability_service import ProbabilityService


# --- Mock providers ---


class MockDrawReader:
    """In-memory draw provider for testing."""

    def __init__(self, draws: list[DrawRow]):
        self._draws = draws

    def iter_draws(self, lottery_id, after_draw_number=None):
        for d in self._draws:
            if after_draw_number is None or d.draw_number > after_draw_number:
                yield d

    def lottery_rules(self, lottery_id):
        return LotteryRules(min_number=1, max_number=49, numbers_to_select=6)


class MockStatsReader:
    """In-memory stats snapshot reader for testing."""

    def __init__(self, frequencies: dict[int, int] | None = None):
        self._frequencies = frequencies or {}

    def active(self, lottery_id, metric_set="core"):
        if self._frequencies:
            return type("Ref", (), {"id": 1, "snapshot_id": 1})()
        return None

    def frequencies(self, snapshot_id):
        return self._frequencies


class MockFeatureReader:
    """In-memory feature snapshot reader for testing."""

    def active(self, lottery_id, feature_set="core"):
        return None


# --- Fake lottery ORM ---


class FakeLottery:
    """Minimal lottery object for service resolution."""

    def __init__(self, id=1, min_number=1, max_number=49, numbers_to_select=6):
        self.id = id
        self.min_number = min_number
        self.max_number = max_number
        self.numbers_to_select = numbers_to_select


class FakeLotteryRepo:
    """In-memory lottery repository."""

    def __init__(self):
        self._lotteries = {1: FakeLottery()}

    def get(self, lottery_id):
        return self._lotteries.get(lottery_id)

    def get_by_code(self, code):
        return self._lotteries.get(1)


# --- Fixtures ---


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.close()


@pytest.fixture()
def sample_draws():
    """10 sample draws for testing."""
    return [
        DrawRow(draw_number=i, numbers=tuple(range(1 + (i % 5), 7 + (i % 5))))
        for i in range(1, 11)
    ]


@pytest.fixture()
def service(session, sample_draws):
    """ProbabilityService with mock providers."""
    draw_reader = MockDrawReader(sample_draws)
    stats_reader = MockStatsReader(frequencies={1: 10, 2: 15, 3: 5})
    feature_reader = MockFeatureReader()
    return ProbabilityService(
        session,
        draw_reader=draw_reader,
        stats_reader=stats_reader,
        feature_reader=feature_reader,
    )


# --- Tests (T-12) ---


class TestProbabilityServiceGenerate:
    """Generation: creates active snapshot, idempotent, handles errors."""

    def test_generate_creates_active_snapshot(self, service, session):
        # Patch _resolve_lottery to return FakeLottery
        service._resolve_lottery = lambda **kw: FakeLottery()
        snap = service.generate(lottery_id=1, scope="full")
        assert snap.status == "active"
        assert snap.lottery_id == 1
        assert snap.model_set == "core"
        assert int(snap.version) >= 1

    def test_generate_idempotent_incremental(self, service, session):
        service._resolve_lottery = lambda **kw: FakeLottery()
        snap1 = service.generate(lottery_id=1, scope="full")
        # Same inputs → incremental returns same snapshot
        snap2 = service.generate(lottery_id=1, scope="incremental")
        assert snap1.id == snap2.id

    def test_generate_full_always_new_version(self, service, session):
        service._resolve_lottery = lambda **kw: FakeLottery()
        snap1 = service.generate(lottery_id=1, scope="full")
        snap2 = service.generate(lottery_id=1, scope="full")
        assert snap1.id != snap2.id
        assert int(snap2.version) > int(snap1.version)

    def test_empty_draws_generates_zero_range(self, service, session):
        service._draw_reader = MockDrawReader([])
        service._resolve_lottery = lambda **kw: FakeLottery()
        snap = service.generate(lottery_id=1, scope="full")
        assert snap.draws_from == 0
        assert snap.draws_to == 0
        assert snap.draw_count == 0

    def test_invalid_scope_raises(self, service):
        service._resolve_lottery = lambda **kw: FakeLottery()
        with pytest.raises(Exception, match="unsupported scope"):
            service.generate(lottery_id=1, scope="bogus")

    def test_invalid_model_set_raises(self, service):
        service._resolve_lottery = lambda **kw: FakeLottery()
        with pytest.raises(Exception, match="unsupported model_set"):
            service.generate(lottery_id=1, model_set="invalid")


class TestProbabilityServiceRead:
    """Read: from stored snapshot, 404 on missing."""

    def test_read_returns_values(self, service, session):
        service._resolve_lottery = lambda **kw: FakeLottery()
        service.generate(lottery_id=1, scope="full")
        snapshot, rows = service.read_values(lottery_id=1)
        assert snapshot.status == "active"
        assert len(rows) > 0

    def test_read_missing_snapshot_raises(self, service):
        service._resolve_lottery = lambda **kw: FakeLottery()
        with pytest.raises(Exception, match="no prob snapshot"):
            service.read_values(lottery_id=999)

    def test_read_never_precomputes(self, service, session):
        """Read without generate should fail, not trigger computation."""
        service._resolve_lottery = lambda **kw: FakeLottery()
        with pytest.raises(Exception, match="no prob snapshot"):
            service.read_values(lottery_id=1)
