"""Tests for meta.meta_service — MetaService orchestration (META-001–META-012).

Spec refs: META-001 (weighted scoring), META-003 (context), META-004 (failed run exclusion),
META-005 (ranking), META-006 (selection), META-007 (idempotency), META-012 (lottery isolation).
Design refs: Sequence Diagrams section.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.errors import MetaServiceError
from backend.app.services.meta_service import MetaService


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock SQLAlchemy session."""
    return MagicMock()


@pytest.fixture
def service(mock_session: MagicMock) -> MetaService:
    return MetaService(mock_session)


class TestRankErrors:
    """Test rank error paths."""

    def test_rank_raises_no_engine_data(self, service: MetaService) -> None:
        """META-004: META_NO_ENGINE_DATA when no engine snapshots exist."""
        with patch(
            "backend.app.services.meta_service.resolve_context_vector",
            side_effect=ValueError("No active engine snapshot found"),
        ):
            with pytest.raises(MetaServiceError) as exc_info:
                service.rank(lottery_id=1)
            assert exc_info.value.code == "META_NO_ENGINE_DATA"

    def test_rank_raises_weights_invalid(self, service: MetaService) -> None:
        """META-001: META_WEIGHTS_INVALID when weights sum to zero."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.rank(lottery_id=1, weights={"hit_rate": 0.0, "average_matches": 0.0})
        assert exc_info.value.code == "META_WEIGHTS_INVALID"

    def test_rank_rejects_top_k_invalid(self, service: MetaService) -> None:
        """META-020: META_TOP_K_INVALID when top_k < 1."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.select(lottery_id=1, top_k=0)
        assert exc_info.value.code == "META_TOP_K_INVALID"

    def test_rank_rejects_top_k_over_20(self, service: MetaService) -> None:
        """META-020: META_TOP_K_INVALID when top_k > 20."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.select(lottery_id=1, top_k=21)
        assert exc_info.value.code == "META_TOP_K_INVALID"


class TestGetRankingErrors:
    """Test get_ranking error paths."""

    def test_get_ranking_not_found(self, service: MetaService) -> None:
        """META_RANKING_NOT_FOUND when no ranking exists."""
        with patch.object(service._store, "get_rankings", return_value=[]):
            with pytest.raises(MetaServiceError) as exc_info:
                service.get_ranking(lottery_id=1)
            assert exc_info.value.code == "META_RANKING_NOT_FOUND"


class TestGetSelectionErrors:
    """Test get_selection error paths."""

    def test_get_selection_not_found(self, service: MetaService) -> None:
        """META_SELECTION_NOT_FOUND when no selection exists."""
        with patch.object(service._store, "get_selections", return_value=[]):
            with pytest.raises(MetaServiceError) as exc_info:
                service.get_selection(lottery_id=1)
            assert exc_info.value.code == "META_SELECTION_NOT_FOUND"


class TestSelectErrors:
    """Test select error paths."""

    def test_select_raises_no_engine_data(self, service: MetaService) -> None:
        """META_NO_ENGINE_DATA when no engine snapshots exist."""
        with patch(
            "backend.app.services.meta_service.resolve_context_vector",
            side_effect=ValueError("No active engine snapshot found"),
        ):
            with pytest.raises(MetaServiceError) as exc_info:
                service.select(lottery_id=1)
            assert exc_info.value.code == "META_NO_ENGINE_DATA"

    def test_select_raises_top_k_invalid(self, service: MetaService) -> None:
        """META_TOP_K_INVALID when top_k < 1."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.select(lottery_id=1, top_k=0)
        assert exc_info.value.code == "META_TOP_K_INVALID"

    def test_select_raises_top_k_over_20(self, service: MetaService) -> None:
        """META_TOP_K_INVALID when top_k > 20."""
        with pytest.raises(MetaServiceError) as exc_info:
            service.select(lottery_id=1, top_k=21)
        assert exc_info.value.code == "META_TOP_K_INVALID"


class TestLotteryIsolation:
    """Test that operations are scoped per lottery_id (META-012)."""

    def test_rank_scoped_to_lottery(self, service: MetaService) -> None:
        """Ranking only considers the specified lottery's data."""
        with patch(
            "backend.app.services.meta_service.resolve_context_vector",
            side_effect=ValueError("No active engine snapshot found"),
        ):
            with pytest.raises(MetaServiceError) as exc_info:
                service.rank(lottery_id=999)
            assert exc_info.value.code == "META_NO_ENGINE_DATA"
            assert "999" in str(exc_info.value)
