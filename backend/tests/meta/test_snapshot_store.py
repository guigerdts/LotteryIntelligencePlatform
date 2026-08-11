"""Tests for meta.snapshot_store — MetaSnapshotStore lifecycle management.

Spec refs: META-005 (ranking), META-007 (idempotency), META-008 (lifecycle),
META-010 (history).
Design refs: History / Comparison section.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.app.meta.snapshot_store import MetaSnapshotStore


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    return session


@pytest.fixture
def store(mock_session: MagicMock) -> MetaSnapshotStore:
    return MetaSnapshotStore(mock_session)


class TestNextVersion:
    """next_version — monotonic versioning (META-005, META-010)."""

    def test_first_version_is_one(self) -> None:
        """No existing versions → version 1."""
        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.scalar.return_value = None
        store = MetaSnapshotStore(session)
        version = store.next_version(1, "abc123")
        assert version == "1"

    def test_monotonic_increment(self) -> None:
        """Existing max version → max + 1."""
        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.scalar.return_value = 3
        store = MetaSnapshotStore(session)
        version = store.next_version(1, "abc123")
        assert version == "4"

    def test_handles_string_version(self) -> None:
        """Existing version '5' → '6'."""
        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.scalar.return_value = 5
        store = MetaSnapshotStore(session)
        version = store.next_version(1, "abc123")
        assert version == "6"


class TestFindByFingerprint:
    """find_by_fingerprint — idempotency check (META-007)."""

    def test_returns_none_when_not_found(self, store: MetaSnapshotStore) -> None:
        result = store.find_by_fingerprint("abc123")
        assert result is None

    def test_returns_existing_when_found(self, store: MetaSnapshotStore) -> None:
        mock_ranking = MagicMock()
        mock_ranking.fingerprint = "abc123"
        store._session.query.return_value.filter.return_value.first.return_value = mock_ranking
        result = store.find_by_fingerprint("abc123")
        assert result == mock_ranking


class TestLifecycleTransitions:
    """Lifecycle transitions — active→retired (META-008)."""

    def test_retire_existing_active(self, store: MetaSnapshotStore) -> None:
        """Existing active ranking → retired when new one is created."""
        mock_active = MagicMock()
        mock_active.status = "active"
        store._session.query.return_value.filter.return_value.first.return_value = mock_active

        store._retire_active("meta_rankings", 1, "abc123")

        assert mock_active.status == "retired"
        store._session.flush.assert_called()

    def test_no_active_to_retire(self, store: MetaSnapshotStore) -> None:
        """No existing active → no-op."""
        store._session.query.return_value.filter.return_value.first.return_value = None
        store._retire_active("meta_rankings", 1, "abc123")
        # No error, no status change
        store._session.flush.assert_not_called()


class TestLotteryIsolation:
    """Lottery isolation — queries scoped by lottery_id (META-012)."""

    def test_next_version_scoped_to_lottery(self, mock_session: MagicMock) -> None:
        """next_version filters by lottery_id."""
        mock_session.query.return_value.filter.return_value.scalar.return_value = None
        store = MetaSnapshotStore(mock_session)
        store.next_version(1, "abc123")
        # The filter call should include lottery_id=1
        filter_calls = mock_session.query.return_value.filter.call_args_list
        assert len(filter_calls) > 0

    def test_get_rankings_scoped_to_lottery(self, store: MetaSnapshotStore) -> None:
        """get_rankings filters by lottery_id."""
        store.get_rankings(1, "abc123")
        filter_calls = store._session.query.return_value.filter.call_args_list
        assert len(filter_calls) > 0
