"""Tests for Opt API routes (PR5)."""

from __future__ import annotations

from backend.app.schemas.opt import OptResultRead, OptSnapshotRead, OptTrainOutcome, OptTrainRequest


class TestOptTrainRequest:
    """OptTrainRequest schema tests."""

    def test_defaults(self) -> None:
        """Default request has expected values."""
        req = OptTrainRequest(lottery_id=1)
        assert req.lottery_id == 1
        assert req.optimizer == "ga"
        assert req.metric == "f1"
        assert req.direction == "maximize"
        assert req.seed == 42

    def test_custom(self) -> None:
        """Custom request values."""
        req = OptTrainRequest(
            lottery_id=2,
            optimizer="pso",
            metric="roc_auc",
            direction="minimize",
            seed=123,
        )
        assert req.optimizer == "pso"
        assert req.metric == "roc_auc"
        assert req.direction == "minimize"
        assert req.seed == 123


class TestOptTrainOutcome:
    """OptTrainOutcome schema tests."""

    def test_with_error(self) -> None:
        """Outcome with error."""
        outcome = OptTrainOutcome(
            optimizer="ga",
            lottery_id=1,
            status="failed",
            fingerprint="",
            error="test error",
        )
        assert outcome.status == "failed"
        assert outcome.error == "test error"

    def test_with_success(self) -> None:
        """Outcome with success."""
        outcome = OptTrainOutcome(
            optimizer="ga",
            lottery_id=1,
            status="active",
            fingerprint="abc123",
            snapshot_id=1,
            best_fitness=0.85,
            n_evaluations=50,
        )
        assert outcome.best_fitness == 0.85
        assert outcome.n_evaluations == 50


class TestOptSnapshotRead:
    """OptSnapshotRead schema tests."""

    def test_read(self) -> None:
        """Snapshot read."""
        snapshot = OptSnapshotRead(
            id=1,
            lottery_id=1,
            optimizer="ga",
            model_set="core-4",
            version="1",
            status="active",
            fingerprint="abc123",
            objective_metric="f1",
            objective_direction="maximize",
        )
        assert snapshot.optimizer == "ga"
        assert snapshot.objective_metric == "f1"


class TestOptResultRead:
    """OptResultRead schema tests."""

    def test_read(self) -> None:
        """Result read."""
        result = OptResultRead(
            target_model="ga",
            fitness=0.85,
            params_json="{}",
            convergence_json="[]",
        )
        assert result.fitness == 0.85
