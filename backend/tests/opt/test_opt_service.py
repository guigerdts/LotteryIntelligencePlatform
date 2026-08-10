"""Tests for OptService (PR5)."""

from __future__ import annotations

import pytest

from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.search_space import SearchParam, SearchSpace
from backend.app.services.opt_service import OptService, TrainOutcome


class TestTrainOutcome:
    """TrainOutcome dataclass tests."""

    def test_defaults(self) -> None:
        """Default outcome has expected fields."""
        outcome = TrainOutcome(
            optimizer="ga",
            lottery_id=1,
            status="active",
            fingerprint="abc123",
        )
        assert outcome.optimizer == "ga"
        assert outcome.lottery_id == 1
        assert outcome.status == "active"
        assert outcome.fingerprint == "abc123"
        assert outcome.snapshot_id is None
        assert outcome.best_fitness is None
        assert outcome.n_evaluations is None
        assert outcome.error is None

    def test_with_error(self) -> None:
        """Outcome with error."""
        outcome = TrainOutcome(
            optimizer="pso",
            lottery_id=2,
            status="failed",
            fingerprint="",
            error="test error",
        )
        assert outcome.status == "failed"
        assert outcome.error == "test error"

    def test_immutability(self) -> None:
        """Outcome is frozen."""
        outcome = TrainOutcome(
            optimizer="ga",
            lottery_id=1,
            status="active",
            fingerprint="abc",
        )
        with pytest.raises(AttributeError):
            outcome.status = "failed"  # type: ignore[misc]


class TestOptServiceInit:
    """OptService initialization tests."""

    def test_init_with_defaults(self) -> None:
        """OptService initializes with default termination."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
        )
        assert service._lottery_id == 1
        assert service._optimizer == "ga"
        assert service._metric == "f1"
        assert service._direction == "maximize"
        assert service._seed == 42

    def test_init_with_custom_config(self) -> None:
        """OptService initializes with custom config."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        termination = TerminationConfig(termination="early_stopping", patience=10)
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=2,
            optimizer="pso",
            metric="roc_auc",
            direction="minimize",
            seed=123,
            version="2.0.0",
            termination=termination,
        )
        assert service._metric == "roc_auc"
        assert service._direction == "minimize"
        assert service._seed == 123
        assert service._version == "2.0.0"
        assert service._termination.patience == 10


class TestOptServiceProtocol:
    """OptService protocol compliance tests."""

    def test_has_train_method(self) -> None:
        """OptService has train method."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
        )
        assert hasattr(service, "train")
        assert callable(service.train)

    def test_has_get_active_snapshot_method(self) -> None:
        """OptService has get_active_snapshot method."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
        )
        assert hasattr(service, "get_active_snapshot")
        assert callable(service.get_active_snapshot)

    def test_has_get_results_method(self) -> None:
        """OptService has get_results method."""
        search_space = SearchSpace(
            params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
        )
        service = OptService(
            session=None,
            objective_fn=lambda p: 0.5,
            search_space=search_space,
            lottery_id=1,
            optimizer="ga",
        )
        assert hasattr(service, "get_results")
        assert callable(service.get_results)
