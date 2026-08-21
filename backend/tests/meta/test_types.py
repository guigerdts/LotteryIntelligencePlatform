"""Tests for meta.types — frozen dataclasses (ContextVector, WeightConfig, RankingEntry,
SelectionEntry).

Spec refs: META-001 (weight config), META-003 (context vector fields).
Design refs: Domain Types section.
"""

from __future__ import annotations

import pytest

from backend.app.meta.types import (
    ContextVector,
    RankingEntry,
    SelectionEntry,
    WeightConfig,
)


class TestContextVector:
    """ContextVector frozen dataclass — META-003."""

    def test_creation_with_all_fields(self) -> None:
        cv = ContextVector(
            lottery_id=1,
            draws_from=100,
            draws_to=200,
            cut=50,
            window=10,
            engine_type="backtesting",
        )
        assert cv.lottery_id == 1
        assert cv.draws_from == 100
        assert cv.draws_to == 200
        assert cv.cut == 50
        assert cv.window == 10
        assert cv.engine_type == "backtesting"

    def test_creation_with_optional_none_fields(self) -> None:
        cv = ContextVector(
            lottery_id=1,
            draws_from=100,
            draws_to=200,
            cut=None,
            window=None,
            engine_type="ml",
        )
        assert cv.cut is None
        assert cv.window is None

    def test_immutability(self) -> None:
        cv = ContextVector(
            lottery_id=1,
            draws_from=100,
            draws_to=200,
            cut=None,
            window=None,
            engine_type="backtesting",
        )
        with pytest.raises(AttributeError):
            cv.lottery_id = 99  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ContextVector(1, 100, 200, 50, 10, "backtesting")
        b = ContextVector(1, 100, 200, 50, 10, "backtesting")
        assert a == b

    def test_inequality_different_lottery(self) -> None:
        a = ContextVector(1, 100, 200, 50, 10, "backtesting")
        b = ContextVector(2, 100, 200, 50, 10, "backtesting")
        assert a != b


class TestWeightConfig:
    """WeightConfig frozen dataclass — META-001, META-019."""

    def test_default_weights(self) -> None:
        wc = WeightConfig()
        assert wc.hit_rate == 0.3
        assert wc.average_matches == 0.3
        assert wc.consistency_score == 0.2
        assert wc.precision == 0.1
        assert wc.recall == 0.1

    def test_custom_weights(self) -> None:
        wc = WeightConfig(hit_rate=0.5, average_matches=0.3, consistency_score=0.1,
                          precision=0.05, recall=0.05)
        assert wc.hit_rate == 0.5
        assert wc.recall == 0.05

    def test_validate_passes_for_nonzero_sum(self) -> None:
        wc = WeightConfig()
        wc.validate()  # should not raise

    def test_validate_rejects_zero_sum(self) -> None:
        wc = WeightConfig(hit_rate=0.0, average_matches=0.0,
                          consistency_score=0.0, precision=0.0, recall=0.0)
        with pytest.raises(ValueError, match="sum"):
            wc.validate()

    def test_immutability(self) -> None:
        wc = WeightConfig()
        with pytest.raises(AttributeError):
            wc.hit_rate = 0.99  # type: ignore[misc]


class TestRankingEntry:
    """RankingEntry frozen dataclass."""

    def test_creation(self) -> None:
        re = RankingEntry(
            model_id="ml-core-5",
            engine_type="ml",
            score=0.85,
            metrics={"hit_rate": 0.8, "precision": 0.7},
        )
        assert re.model_id == "ml-core-5"
        assert re.score == 0.85
        assert re.metrics == {"hit_rate": 0.8, "precision": 0.7}

    def test_immutability(self) -> None:
        re = RankingEntry("ml-core-5", "ml", 0.85, {"hit_rate": 0.8})
        with pytest.raises(AttributeError):
            re.score = 0.99  # type: ignore[misc]


class TestSelectionEntry:
    """SelectionEntry frozen dataclass."""

    def test_creation(self) -> None:
        se = SelectionEntry(
            model_id="ml-core-5",
            engine_type="ml",
            rank=1,
            score=0.85,
        )
        assert se.rank == 1
        assert se.model_id == "ml-core-5"

    def test_immutability(self) -> None:
        se = SelectionEntry("ml-core-5", "ml", 1, 0.85)
        with pytest.raises(AttributeError):
            se.rank = 2  # type: ignore[misc]
