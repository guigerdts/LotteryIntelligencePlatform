"""ExpService add_run()/_validate_snapshot + update() regressions (EXP-001/003)."""

from __future__ import annotations

import pytest

from backend.app.models.dl_snapshot import DlSnapshot
from backend.app.models.ml_snapshot import MlSnapshot
from backend.app.services.errors import (
    DuplicateExperimentError,
    ExperimentNotFoundError,
    ExpSnapshotNotFoundError,
    ValidationError,
)
from backend.app.services.exp_service import ExpService
from tests.exp_helpers import ML_FP, create_opt_snapshot, seed_lottery, seed_metric_snapshot


@pytest.fixture
def seeded_lottery(db):
    return seed_lottery(db)


class TestUpdateErrors:
    def test_update_nonexistent_experiment(self, db, seeded_lottery) -> None:
        with pytest.raises(ExperimentNotFoundError):
            ExpService(db).update(999, name="Nope")

    def test_update_duplicate_name_raises_domain_error(self, db, seeded_lottery) -> None:
        """T-S3-05: rename-to-existing raises the domain error, not IntegrityError."""
        svc = ExpService(db)
        a = svc.create(lottery_id=1, name="Original")
        b = svc.create(lottery_id=1, name="Other")
        with pytest.raises(DuplicateExperimentError, match="already exists"):
            svc.update(b.experiment_id, name=a.name)

    def test_update_same_name_allowed(self, db, seeded_lottery) -> None:
        """T-S3-05: updating an experiment to its own name stays valid."""
        svc = ExpService(db)
        a = svc.create(lottery_id=1, name="Original")
        outcome = svc.update(a.experiment_id, name="Original", description="touched")
        assert outcome.name == "Original"


class TestAddRunErrors:
    def test_add_run_nonexistent_experiment(self, db, seeded_lottery) -> None:
        with pytest.raises(ExperimentNotFoundError):
            ExpService(db).add_run(
                999, run_label="r1", engine_type="backtesting", engine_snapshot_id=1
            )

    def test_add_run_missing_snapshot_raises(self, db, seeded_lottery) -> None:
        svc = ExpService(db)
        outcome = svc.create(lottery_id=1, name="Missing Snap")
        with pytest.raises(ExpSnapshotNotFoundError):
            svc.add_run(
                outcome.experiment_id,
                run_label="r1",
                engine_type="backtesting",
                engine_snapshot_id=9999,
            )

    def test_add_run_rejects_unknown_engine_type(self, db, seeded_lottery) -> None:
        svc = ExpService(db)
        outcome = svc.create(lottery_id=1, name="Bad Engine")
        with pytest.raises(ValidationError):
            svc.add_run(
                outcome.experiment_id, run_label="r1", engine_type="quantum", engine_snapshot_id=1
            )


class TestValidateSnapshotBranches:
    def test_add_run_optimization_snapshot_valid(self, db, seeded_lottery) -> None:
        """Optimization snapshots carry `fingerprint` — copied as-is."""
        snap_id = create_opt_snapshot(db)
        db.commit()
        svc = ExpService(db)
        outcome = svc.create(lottery_id=1, name="Validate optimization")
        run = svc.add_run(
            outcome.experiment_id,
            run_label="r1",
            engine_type="optimization",
            engine_snapshot_id=snap_id,
        )
        assert run.engine_fingerprint == "fp-opt"

    @pytest.mark.parametrize(
        ("engine_type", "model"),
        [("ml", MlSnapshot), ("dl", DlSnapshot)],
    )
    def test_add_run_ml_dl_valid_uses_input_fingerprint(
        self, db, seeded_lottery, engine_type, model
    ) -> None:
        """T-S3-05: ml/dl add_run succeeds; engine_fingerprint = input_fingerprint.

        Regression: _validate_snapshot read the nonexistent `fingerprint`
        attribute and crashed with AttributeError.
        """
        snap_id = (
            seed_metric_snapshot(db, model, window=20)
            if engine_type == "dl"
            else seed_metric_snapshot(db, model)
        )
        db.commit()
        svc = ExpService(db)
        outcome = svc.create(lottery_id=1, name=f"Validate {engine_type}")
        run = svc.add_run(
            outcome.experiment_id,
            run_label="r1",
            engine_type=engine_type,
            engine_snapshot_id=snap_id,
        )
        assert run.engine_fingerprint == ML_FP
