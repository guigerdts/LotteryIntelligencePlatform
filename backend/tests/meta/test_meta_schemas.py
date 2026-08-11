"""Tests for meta Pydantic schemas (META-013).

Spec refs: META-013 (API endpoints), META-019 (weight config), META-020 (top-k defaults).
Design refs: Data Model section.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.meta import (
    RankRequest,
    RankingResult,
    RankingSnapshot,
    SelectRequest,
    SelectionResult,
    SelectionSnapshot,
)


class TestRankRequest:
    """RankRequest schema validation."""

    def test_minimal(self) -> None:
        req = RankRequest(lottery_id=1)
        assert req.lottery_id == 1
        assert req.engine_types is None
        assert req.weights is None

    def test_with_engine_types(self) -> None:
        req = RankRequest(lottery_id=1, engine_types=["backtesting", "ml"])
        assert req.engine_types == ["backtesting", "ml"]

    def test_with_weights(self) -> None:
        req = RankRequest(lottery_id=1, weights={"hit_rate": 0.5, "average_matches": 0.5})
        assert req.weights == {"hit_rate": 0.5, "average_matches": 0.5}

    def test_rejects_zero_lottery_id(self) -> None:
        with pytest.raises(ValidationError):
            RankRequest(lottery_id=0)

    def test_rejects_negative_lottery_id(self) -> None:
        with pytest.raises(ValidationError):
            RankRequest(lottery_id=-1)

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            RankRequest(lottery_id=1, unknown_field="x")


class TestSelectRequest:
    """SelectRequest schema validation."""

    def test_minimal(self) -> None:
        req = SelectRequest(lottery_id=1)
        assert req.lottery_id == 1
        assert req.top_k is None
        assert req.min_score is None

    def test_with_top_k(self) -> None:
        req = SelectRequest(lottery_id=1, top_k=10)
        assert req.top_k == 10

    def test_with_min_score(self) -> None:
        req = SelectRequest(lottery_id=1, min_score=0.5)
        assert req.min_score == 0.5

    def test_rejects_top_k_zero(self) -> None:
        with pytest.raises(ValidationError):
            SelectRequest(lottery_id=1, top_k=0)

    def test_rejects_top_k_over_20(self) -> None:
        with pytest.raises(ValidationError):
            SelectRequest(lottery_id=1, top_k=21)


class TestRankingResult:
    """RankingResult schema validation."""

    def test_creation(self) -> None:
        result = RankingResult(
            ranking_id=1,
            lottery_id=1,
            context_hash="abc123",
            version="1",
            status="active",
            fingerprint="fp123",
            entries=[{"model_id": "m1", "engine_type": "backtesting", "score": 0.9, "metrics": {}}],
        )
        assert result.ranking_id == 1
        assert len(result.entries) == 1


class TestSelectionResult:
    """SelectionResult schema validation."""

    def test_creation(self) -> None:
        result = SelectionResult(
            selection_id=1,
            lottery_id=1,
            ranking_id=1,
            context_hash="abc123",
            version="1",
            status="active",
            fingerprint="fp123",
            entries=[{"model_id": "m1", "engine_type": "backtesting", "rank": 1, "score": 0.9}],
        )
        assert result.selection_id == 1
        assert len(result.entries) == 1


class TestRankingSnapshot:
    """RankingSnapshot schema validation."""

    def test_creation(self) -> None:
        snap = RankingSnapshot(
            lottery_id=1,
            context_hash="abc123",
            rankings=[{"ranking_id": 1, "version": "1", "status": "active", "fingerprint": "fp"}],
        )
        assert snap.lottery_id == 1
        assert len(snap.rankings) == 1


class TestSelectionSnapshot:
    """SelectionSnapshot schema validation."""

    def test_creation(self) -> None:
        snap = SelectionSnapshot(
            lottery_id=1,
            context_hash="abc123",
            selections=[{"selection_id": 1, "version": "1", "status": "active", "fingerprint": "fp"}],
        )
        assert snap.lottery_id == 1
        assert len(snap.selections) == 1
