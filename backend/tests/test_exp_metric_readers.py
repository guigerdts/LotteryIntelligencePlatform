"""ExpService.compare() metric readers across all engine types — EXP-005 (T-S3-05)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.app.models.bt_snapshot import BtSnapshot
from backend.app.models.dl_metric import DlMetric
from backend.app.models.dl_snapshot import DlSnapshot
from backend.app.models.ml_metric import MlMetric
from backend.app.models.ml_snapshot import MlSnapshot
from backend.app.models.opt_result import OptResult
from backend.app.services.errors import ExpSnapshotNotFoundError
from backend.app.services.exp_service import ExpService
from tests.exp_helpers import create_opt_snapshot, seed_lottery, seed_metric_snapshot


@pytest.fixture
def seeded_lottery(db):
    return seed_lottery(db)


def _seed_metric(db, model, snap_id: int, name: str, value: float, *, number: int = 1) -> None:
    db.add(
        model(
            snapshot_id=snap_id,
            model_id="m",
            model_version="1",
            number=number,
            metric_name=name,
            value=Decimal(str(value)),
            params_json="{}",
        )
    )
    db.flush()


def _create_opt_result(db, snap_id: int, target: str, fitness: float) -> None:
    db.add(
        OptResult(
            snapshot_id=snap_id,
            target_model=target,
            best_params="{}",
            best_fitness=Decimal(str(fitness)),
            convergence_history="[]",
            metrics="{}",
            fingerprint="optres-" + target,
        )
    )
    db.flush()


def _create_bt_snapshot(db, strategy: str, fingerprint: str) -> int:
    snap = BtSnapshot(
        lottery_id=1,
        strategy_id=strategy,
        fingerprint=fingerprint,
        version="1",
        status="active",
        config_json="{}",
    )
    db.add(snap)
    db.flush()
    return snap.id


def _add_runs(db, service: ExpService, run_specs: list[dict]):
    outcome = service.create(lottery_id=1, name="Metric Readers")
    runs = []
    for spec in run_specs:
        run = service.add_run(
            outcome.experiment_id,
            run_label=spec["run_label"],
            engine_type=spec["engine_type"],
            engine_snapshot_id=spec["engine_snapshot_id"],
        )
        runs.append(run)
    db.commit()
    return outcome, runs


def _matrix(result) -> dict:
    return {r["run_label"]: r["metrics"] for r in json.loads(result.comparison_json)["runs"]}


class TestCompareMixedEngines:
    def test_compare_ml_and_dl_runs(self, db, seeded_lottery) -> None:
        svc = ExpService(db)
        ml_snap = seed_metric_snapshot(db, MlSnapshot)
        _seed_metric(db, MlMetric, ml_snap, "f1", 0.85, number=1)
        _seed_metric(db, MlMetric, ml_snap, "f1", 0.80, number=2)
        dl_snap = seed_metric_snapshot(db, DlSnapshot, window=20)
        _seed_metric(db, DlMetric, dl_snap, "accuracy", 0.92)
        db.commit()

        outcome, runs = _add_runs(
            db,
            svc,
            [
                {"run_label": "ml-run", "engine_type": "ml", "engine_snapshot_id": ml_snap},
                {"run_label": "dl-run", "engine_type": "dl", "engine_snapshot_id": dl_snap},
            ],
        )
        result = svc.compare(outcome.experiment_id, run_ids=[r.run_id for r in runs])
        by_label = _matrix(result)
        assert by_label["ml-run"]["f1"] == pytest.approx(0.825)
        assert by_label["dl-run"]["accuracy"] == pytest.approx(0.92)

    def test_compare_optimization_runs(self, db, seeded_lottery) -> None:
        svc = ExpService(db)
        opt_snap = create_opt_snapshot(db)
        _create_opt_result(db, opt_snap, "rf", 0.91)
        _create_opt_result(db, opt_snap, "mlp", 0.87)
        db.commit()

        outcome, runs = _add_runs(
            db,
            svc,
            [
                {
                    "run_label": "opt-run",
                    "engine_type": "optimization",
                    "engine_snapshot_id": opt_snap,
                },
            ],
        )
        opt_snap2 = create_opt_snapshot(db, fingerprint="fp-opt-2")
        _create_opt_result(db, opt_snap2, "rf", 0.90)
        db.commit()
        run2 = svc.add_run(
            outcome.experiment_id,
            run_label="opt-run-2",
            engine_type="optimization",
            engine_snapshot_id=opt_snap2,
        )
        result = svc.compare(outcome.experiment_id, run_ids=[runs[0].run_id, run2.run_id])
        by_label = _matrix(result)
        assert by_label["opt-run"]["best_fitness_rf"] == pytest.approx(0.91)
        assert by_label["opt-run"]["best_fitness_mlp"] == pytest.approx(0.87)

    def test_compare_backtesting_missing_result_returns_empty_metrics(
        self, db, seeded_lottery
    ) -> None:
        snap1 = _create_bt_snapshot(db, "strat-a", "fp-bt-1")
        snap2 = _create_bt_snapshot(db, "strat-b", "fp-bt-2")
        db.commit()

        svc = ExpService(db)
        outcome = svc.create(lottery_id=1, name="BT Missing")
        run1 = svc.add_run(
            outcome.experiment_id,
            run_label="bt-1",
            engine_type="backtesting",
            engine_snapshot_id=snap1,
        )
        run2 = svc.add_run(
            outcome.experiment_id,
            run_label="bt-2",
            engine_type="backtesting",
            engine_snapshot_id=snap2,
        )
        result = svc.compare(outcome.experiment_id, run_ids=[run1.run_id, run2.run_id])
        by_label = _matrix(result)
        assert by_label["bt-1"] == {}
        assert by_label["bt-2"] == {}


class TestCompareMissingRuns:
    def test_compare_unknown_run_id_raises(self, db, seeded_lottery) -> None:
        svc = ExpService(db)
        outcome = svc.create(lottery_id=1, name="Missing Run")
        with pytest.raises(ExpSnapshotNotFoundError):
            svc.compare(outcome.experiment_id, run_ids=[1, 999])


class TestDlMetricAveraging:
    def test_dl_duplicate_metric_averaged(self, db, seeded_lottery) -> None:
        dl_snap = seed_metric_snapshot(db, DlSnapshot, window=20)
        _seed_metric(db, DlMetric, dl_snap, "accuracy", 0.90, number=1)
        _seed_metric(db, DlMetric, dl_snap, "accuracy", 0.94, number=2)
        db.commit()

        svc = ExpService(db)
        outcome, runs = _add_runs(
            db,
            svc,
            [
                {"run_label": "dl-a", "engine_type": "dl", "engine_snapshot_id": dl_snap},
                {"run_label": "dl-b", "engine_type": "dl", "engine_snapshot_id": dl_snap},
            ],
        )
        result = svc.compare(outcome.experiment_id, run_ids=[r.run_id for r in runs])
        by_label = _matrix(result)
        assert by_label["dl-a"]["accuracy"] == pytest.approx(0.92)
