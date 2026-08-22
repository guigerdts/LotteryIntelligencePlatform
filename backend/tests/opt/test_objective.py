"""Tests for ObjectiveFunction and ObjectiveConfig (PR4)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.app.opt.objective import (
    SUPPORTED_DIRECTIONS,
    SUPPORTED_METRICS,
    DlObjectiveFunction,
    MlObjectiveFunction,
    ObjectiveConfig,
)


class TestObjectiveConfig:
    """ObjectiveConfig tests."""

    def test_defaults(self) -> None:
        """Default config: f1, maximize."""
        cfg = ObjectiveConfig()
        assert cfg.metric == "f1"
        assert cfg.direction == "maximize"

    def test_custom(self) -> None:
        """Custom config."""
        cfg = ObjectiveConfig(metric="roc_auc", direction="minimize")
        assert cfg.metric == "roc_auc"
        assert cfg.direction == "minimize"

    def test_immutability(self) -> None:
        """Config is frozen."""
        cfg = ObjectiveConfig()
        with pytest.raises(AttributeError):
            cfg.metric = "accuracy"  # type: ignore[misc]


class TestSupportedMetrics:
    """SUPPORTED_METRICS tests."""

    def test_contains_core_5(self) -> None:
        """All five metrics present."""
        assert SUPPORTED_METRICS == {"f1", "roc_auc", "accuracy", "precision", "recall"}

    def test_frozen(self) -> None:
        """Set is immutable."""
        assert isinstance(SUPPORTED_METRICS, frozenset)


class TestSupportedDirections:
    """SUPPORTED_DIRECTIONS tests."""

    def test_maximize_minimize(self) -> None:
        """Both directions present."""
        assert SUPPORTED_DIRECTIONS == {"maximize", "minimize"}


class TestMlObjectiveFunction:
    """MlObjectiveFunction tests (unit — no real training)."""

    def test_instantiation(self) -> None:
        """Can create with defaults."""
        fn = MlObjectiveFunction(
            family="svm",
            lottery_id=1,
            records=[],
            snapshot_id=1,
            feature_rows=[],
        )
        assert fn._family == "svm"
        assert fn._config.metric == "f1"
        assert fn._config.direction == "maximize"

    def test_custom_config(self) -> None:
        """Custom config propagated."""
        cfg = ObjectiveConfig(metric="accuracy", direction="minimize")
        fn = MlObjectiveFunction(
            family="rf",
            lottery_id=2,
            records=[],
            snapshot_id=1,
            feature_rows=[],
            config=cfg,
        )
        assert fn._config.metric == "accuracy"
        assert fn._config.direction == "minimize"


class TestDlObjectiveFunction:
    """DlObjectiveFunction tests (unit — no real training)."""

    def test_instantiation(self) -> None:
        """Can create with defaults."""
        fn = DlObjectiveFunction(
            family="mlp",
            train_batch=None,
            eval_batch=None,
        )
        assert fn._family == "mlp"
        assert fn._config.metric == "f1"
        assert fn._config.direction == "maximize"

    def test_custom_config(self) -> None:
        """Custom config propagated."""
        cfg = ObjectiveConfig(metric="roc_auc", direction="minimize")
        fn = DlObjectiveFunction(
            family="lstm",
            train_batch=None,
            eval_batch=None,
            config=cfg,
        )
        assert fn._config.metric == "roc_auc"
        assert fn._config.direction == "minimize"


class TestProtocolCompliance:
    """ObjectiveFunction protocol tests."""

    def test_ml_satisfies_protocol(self) -> None:
        """MlObjectiveFunction has evaluate method."""
        fn = MlObjectiveFunction(
            family="svm",
            lottery_id=1,
            records=[],
            snapshot_id=1,
            feature_rows=[],
        )
        assert hasattr(fn, "evaluate")
        assert callable(fn.evaluate)

    def test_dl_satisfies_protocol(self) -> None:
        """DlObjectiveFunction has evaluate method."""
        fn = DlObjectiveFunction(
            family="mlp",
            train_batch=None,
            eval_batch=None,
        )
        assert hasattr(fn, "evaluate")
        assert callable(fn.evaluate)


class TestDlObjectiveCutThreading:
    """evaluate() threads ``cut`` from params into dl.engine.train (DLE-05).

    The engine now REQUIRES a declared cut, so evaluate must always pass one;
    ephemeral fitness runs default to 0 and are never persisted.
    """

    def _evaluate_capture_train(self, params: dict[str, object]) -> MagicMock:
        """Run evaluate() with dl.engine.train patched out; return the mock."""
        stub = MagicMock()
        stub.metrics = {"f1": Decimal("0.5")}
        with patch("backend.app.dl.engine.train", return_value=stub) as mock_train:
            fn = DlObjectiveFunction(family="mlp", train_batch=None, eval_batch=None)
            fitness = fn.evaluate(params)
        assert fitness == Decimal("0.50000000")
        return mock_train

    def test_explicit_cut_threaded(self) -> None:
        """Params carrying ``cut`` reach the engine call."""
        mock_train = self._evaluate_capture_train({"cut": 42})
        assert mock_train.call_args.kwargs["cut"] == 42

    def test_missing_cut_defaults_to_zero(self) -> None:
        """Absent ``cut`` falls back to 0 (ephemeral run)."""
        mock_train = self._evaluate_capture_train({})
        assert mock_train.call_args.kwargs["cut"] == 0
