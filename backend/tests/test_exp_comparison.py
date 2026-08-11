"""Tests for ExpService.compare() — EXP-005, NFR-EXP-02/03/04.

Strict TDD: these tests reference ``ExpService.compare()`` which does NOT exist yet.
Run them → they MUST FAIL (ImportError or AttributeError). Then implement compare().
"""

import json

import pytest

from backend.app.models.lottery import Lottery
from backend.app.services.errors import ComparisonInsufficientRunsError, ExperimentNotFoundError
from backend.app.services.exp_service import ExpService


@pytest.fixture
def seeded_lottery(db):
    """Seed a lottery row for FK compliance."""
    lottery = Lottery(
        id=1,
        code="TEST",
        name="Test Lottery",
        country="US",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
    )
    db.add(lottery)
    db.commit()
    return lottery


def _create_bt_snapshot(db, lottery_id: int, *, fingerprint: str = "fp_aaa") -> int:
    """Insert a bt_snapshots row and return its id."""
    from backend.app.models.bt_snapshot import BtSnapshot

    snap = BtSnapshot(
        lottery_id=lottery_id,
        strategy_id="strat-a",
        fingerprint=fingerprint,
        version="1",
        status="active",
        config_json="{}",
    )
    db.add(snap)
    db.flush()
    return snap.id


def _create_bt_result(db, snapshot_id: int, metrics: dict) -> int:
    """Insert a bt_results row with aggregate_metrics_json."""
    from backend.app.models.bt_result import BtResult

    row = BtResult(
        snapshot_id=snapshot_id,
        aggregate_metrics_json=json.dumps(metrics),
        window_history_json="[]",
    )
    db.add(row)
    db.flush()
    return row.id


def _create_experiment_with_runs(db, service: ExpService, run_specs: list[dict]):
    """Create an experiment and add runs from run_specs.

    Each spec: {run_label, engine_type, engine_snapshot_id, fingerprint}
    """
    outcome = service.create(lottery_id=1, name="Compare Test")
    runs = []
    for spec in run_specs:
        run = service.add_run(
            outcome.experiment_id,
            run_label=spec["run_label"],
            engine_type=spec["engine_type"],
            engine_snapshot_id=spec["engine_snapshot_id"],
        )
        runs.append(run)
    return outcome, runs


class TestCompareInsufficientRuns:
    """COMPARISON_INSUFFICIENT_RUNS: < 2 runs → error."""

    def test_compare_single_run_raises(self, db, seeded_lottery):
        """Comparing with only 1 run raises ComparisonInsufficientRunsError."""
        service = ExpService(db)
        snap_id = _create_bt_snapshot(db, 1)
        outcome, _ = _create_experiment_with_runs(
            db,
            service,
            [{"run_label": "only", "engine_type": "backtesting", "engine_snapshot_id": snap_id}],
        )
        with pytest.raises(ComparisonInsufficientRunsError) as exc_info:
            service.compare(outcome.experiment_id, run_ids=[1])
        assert exc_info.value.code == "COMPARISON_INSUFFICIENT_RUNS"

    def test_compare_empty_runs_raises(self, db, seeded_lottery):
        """Comparing with 0 runs raises ComparisonInsufficientRunsError."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Empty Compare")
        with pytest.raises(ComparisonInsufficientRunsError):
            service.compare(outcome.experiment_id, run_ids=[])


class TestCompareTwoRuns:
    """2-run comparison matrix correctness."""

    def test_compare_two_bt_runs(self, db, seeded_lottery):
        """Comparing two backtesting runs produces correct matrix."""
        service = ExpService(db)
        snap_a = _create_bt_snapshot(db, 1, fingerprint="fp_aaa")
        snap_b = _create_bt_snapshot(db, 1, fingerprint="fp_bbb")
        _create_bt_result(db, snap_a, {"hit_rate": 0.12, "average_matches": 2.1})
        _create_bt_result(db, snap_b, {"hit_rate": 0.18, "average_matches": 3.0})

        outcome, runs = _create_experiment_with_runs(
            db,
            service,
            [
                {"run_label": "alpha", "engine_type": "backtesting", "engine_snapshot_id": snap_a},
                {"run_label": "beta", "engine_type": "backtesting", "engine_snapshot_id": snap_b},
            ],
        )

        result = service.compare(
            outcome.experiment_id,
            run_ids=[runs[0].run_id, runs[1].run_id],
        )

        # Parse the comparison_json
        matrix = json.loads(result.comparison_json)
        assert matrix["experiment_id"] == outcome.experiment_id
        assert len(matrix["runs"]) == 2

        # Sorted by run_label alphabetically: alpha < beta
        assert matrix["runs"][0]["run_label"] == "alpha"
        assert matrix["runs"][0]["metrics"]["hit_rate"] == 0.12
        assert matrix["runs"][1]["run_label"] == "beta"
        assert matrix["runs"][1]["metrics"]["hit_rate"] == 0.18

        # metric_names is a sorted list of all metric keys
        assert "hit_rate" in matrix["metric_names"]
        assert "average_matches" in matrix["metric_names"]

    def test_compare_sorted_by_run_label(self, db, seeded_lottery):
        """Comparison matrix is sorted by run_label alphabetically."""
        service = ExpService(db)
        snap1 = _create_bt_snapshot(db, 1, fingerprint="fp_111")
        snap2 = _create_bt_snapshot(db, 1, fingerprint="fp_222")
        snap3 = _create_bt_snapshot(db, 1, fingerprint="fp_333")
        _create_bt_result(db, snap1, {"f1": 0.5})
        _create_bt_result(db, snap2, {"f1": 0.6})
        _create_bt_result(db, snap3, {"f1": 0.7})

        outcome, runs = _create_experiment_with_runs(
            db,
            service,
            [
                {"run_label": "charlie", "engine_type": "backtesting", "engine_snapshot_id": snap1},
                {"run_label": "alpha", "engine_type": "backtesting", "engine_snapshot_id": snap2},
                {"run_label": "bravo", "engine_type": "backtesting", "engine_snapshot_id": snap3},
            ],
        )

        result = service.compare(
            outcome.experiment_id,
            run_ids=[runs[0].run_id, runs[1].run_id, runs[2].run_id],
        )
        matrix = json.loads(result.comparison_json)

        labels = [r["run_label"] for r in matrix["runs"]]
        assert labels == ["alpha", "bravo", "charlie"]


class TestCompareIdempotent:
    """Same (experiment_id, run_ids) → return cached comparison."""

    def test_compare_same_runs_returns_cached(self, db, seeded_lottery):
        """Comparing same runs twice returns the same comparison (idempotent)."""
        service = ExpService(db)
        snap_a = _create_bt_snapshot(db, 1, fingerprint="fp_xxx")
        snap_b = _create_bt_snapshot(db, 1, fingerprint="fp_yyy")
        _create_bt_result(db, snap_a, {"hit_rate": 0.10})
        _create_bt_result(db, snap_b, {"hit_rate": 0.20})

        outcome, runs = _create_experiment_with_runs(
            db,
            service,
            [
                {"run_label": "run1", "engine_type": "backtesting", "engine_snapshot_id": snap_a},
                {"run_label": "run2", "engine_type": "backtesting", "engine_snapshot_id": snap_b},
            ],
        )

        run_ids = sorted([runs[0].run_id, runs[1].run_id])
        result1 = service.compare(outcome.experiment_id, run_ids=run_ids)
        result2 = service.compare(outcome.experiment_id, run_ids=run_ids)

        assert result1.comparison_json == result2.comparison_json

    def test_different_run_ids_produce_different_comparison(self, db, seeded_lottery):
        """Different run_id sets produce different comparison JSON."""
        service = ExpService(db)
        snap_a = _create_bt_snapshot(db, 1, fingerprint="fp_a")
        snap_b = _create_bt_snapshot(db, 1, fingerprint="fp_b")
        snap_c = _create_bt_snapshot(db, 1, fingerprint="fp_c")
        _create_bt_result(db, snap_a, {"hit_rate": 0.10})
        _create_bt_result(db, snap_b, {"hit_rate": 0.20})
        _create_bt_result(db, snap_c, {"hit_rate": 0.30})

        outcome, runs = _create_experiment_with_runs(
            db,
            service,
            [
                {"run_label": "run1", "engine_type": "backtesting", "engine_snapshot_id": snap_a},
                {"run_label": "run2", "engine_type": "backtesting", "engine_snapshot_id": snap_b},
                {"run_label": "run3", "engine_type": "backtesting", "engine_snapshot_id": snap_c},
            ],
        )

        # Compare pair (run1, run2) vs pair (run1, run3)
        result_a = service.compare(
            outcome.experiment_id,
            run_ids=[runs[0].run_id, runs[1].run_id],
        )
        result_b = service.compare(
            outcome.experiment_id,
            run_ids=[runs[0].run_id, runs[2].run_id],
        )

        assert result_a.comparison_json != result_b.comparison_json


class TestCompareNonexistentExperiment:
    """Comparing non-existent experiment raises error."""

    def test_compare_nonexistent_experiment(self, db, seeded_lottery):
        """Comparing a non-existent experiment raises ExperimentNotFoundError."""
        service = ExpService(db)
        with pytest.raises(ExperimentNotFoundError):
            service.compare(999, run_ids=[1, 2])
