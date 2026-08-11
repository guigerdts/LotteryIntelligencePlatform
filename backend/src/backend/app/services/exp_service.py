"""ExpService — experiment service layer (EXP-001/002/003/004/005/006).

Exposes experiment CRUD, run association, comparison, and export through
a service boundary. API and CLI call this layer; the service owns DB
access, validation, and persistence via ``ExpSnapshotStore``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.experiments.fingerprint import compute_exp_fingerprint
from backend.app.experiments.snapshot_store import ExpSnapshotStore
from backend.app.exporters.experiment_exporter import ExperimentExporter
from backend.app.models.exp_comparison import ExpComparison
from backend.app.models.exp_experiment import ExpExperiment
from backend.app.models.exp_run import ExpRun
from backend.app.services.errors import (
    ComparisonInsufficientRunsError,
    DuplicateExperimentError,
    ExperimentNotFoundError,
    ExperimentRetiredError,
    ExportFormatInvalidError,
    ExpSnapshotNotFoundError,
    NotFoundError,
    ValidationError,
)

# Engine table mapping for snapshot validation (EXP-003)
ENGINE_TABLES = {
    "backtesting": "bt_snapshots",
    "ml": "ml_snapshots",
    "dl": "dl_snapshots",
    "optimization": "opt_snapshots",
}


@dataclass(frozen=True)
class ExperimentOutcome:
    """Result of experiment creation/update."""

    experiment_id: int
    lottery_id: int
    name: str
    fingerprint: str
    version: str
    status: str


@dataclass(frozen=True)
class ExperimentEntry:
    """Experiment data for list/read operations."""

    experiment_id: int
    lottery_id: int
    name: str
    description: str | None
    fingerprint: str
    version: str
    status: str
    config_json: str | None
    created_at: str


@dataclass(frozen=True)
class RunOutcome:
    """Result of run association."""

    run_id: int
    experiment_id: int
    run_label: str
    engine_type: str
    engine_snapshot_id: int
    engine_fingerprint: str
    notes: str | None


@dataclass(frozen=True)
class ComparisonOutcome:
    """Result of comparison persistence."""

    comparison_id: int
    experiment_id: int
    comparison_json: str
    created_at: str


class ExpService:
    """Experiment service (EXP-001). API and CLI call this layer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        lottery_id: int,
        name: str,
        description: str | None = None,
        config_json: str | None = None,
    ) -> ExperimentOutcome:
        """Create a new experiment (EXP-001)."""
        self._resolve_lottery(lottery_id)

        # Compute fingerprint for idempotency check
        fingerprint = compute_exp_fingerprint(
            name=name,
            lottery_id=lottery_id,
            config_json=config_json,
            description=description,
            status="active",
        )

        store = ExpSnapshotStore(self._session)

        # Check for idempotent create (same fingerprint returns existing)
        existing = store.find_by_fingerprint(fingerprint)
        if existing is not None:
            return ExperimentOutcome(
                experiment_id=existing.id,
                lottery_id=existing.lottery_id,
                name=existing.name,
                fingerprint=existing.fingerprint,
                version=existing.version,
                status=existing.status,
            )

        # Check for duplicate name within lottery (different fingerprint)
        self._check_duplicate_name(lottery_id, name, fingerprint)

        version = store.next_version(lottery_id, name)
        experiment = store.create(
            lottery_id=lottery_id,
            name=name,
            description=description,
            status="active",
            fingerprint=fingerprint,
            version=version,
            config_json=config_json,
        )
        self._session.commit()

        return ExperimentOutcome(
            experiment_id=experiment.id,
            lottery_id=lottery_id,
            name=name,
            fingerprint=fingerprint,
            version=version,
            status="active",
        )

    def get(self, experiment_id: int) -> ExperimentEntry:
        """Get experiment by ID (EXP-001)."""
        store = ExpSnapshotStore(self._session)
        experiment = store.get(experiment_id)
        if experiment is None:
            raise ExperimentNotFoundError(f"experiment {experiment_id} not found")
        return ExperimentEntry(
            experiment_id=experiment.id,
            lottery_id=experiment.lottery_id,
            name=experiment.name,
            description=experiment.description,
            fingerprint=experiment.fingerprint,
            version=experiment.version,
            status=experiment.status,
            config_json=experiment.config_json,
            created_at=experiment.created_at.isoformat(),
        )

    def update(
        self,
        experiment_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        config_json: str | None = None,
    ) -> ExperimentOutcome:
        """Update experiment fields (EXP-001)."""
        store = ExpSnapshotStore(self._session)
        experiment = store.get(experiment_id)
        if experiment is None:
            raise ExperimentNotFoundError(f"experiment {experiment_id} not found")

        # Check if experiment is retired (immutability)
        if experiment.status == "retired":
            raise ExperimentRetiredError("cannot update retired experiment")

        # Validate status transition
        if status is not None and status not in ("active", "retired", "failed"):
            raise ValidationError(f"invalid status: {status}")

        # Compute new fingerprint for idempotency check
        new_fingerprint = compute_exp_fingerprint(
            name=name if name is not None else experiment.name,
            lottery_id=experiment.lottery_id,
            config_json=config_json if config_json is not None else experiment.config_json,
            description=description if description is not None else experiment.description,
            status=status if status is not None else experiment.status,
        )

        # Check for idempotent update (same fingerprint)
        if new_fingerprint == experiment.fingerprint:
            return ExperimentOutcome(
                experiment_id=experiment.id,
                lottery_id=experiment.lottery_id,
                name=experiment.name,
                fingerprint=experiment.fingerprint,
                version=experiment.version,
                status=experiment.status,
            )

        # Check for duplicate name within lottery (different fingerprint)
        if name is not None and name != experiment.name:
            self._check_duplicate_name(experiment.lottery_id, name, new_fingerprint)

        # Increment version
        new_version = str(int(experiment.version) + 1)

        updated = store.update(
            experiment,
            name=name,
            description=description,
            status=status,
            fingerprint=new_fingerprint,
            version=new_version,
            config_json=config_json,
        )
        self._session.commit()

        return ExperimentOutcome(
            experiment_id=updated.id,
            lottery_id=updated.lottery_id,
            name=updated.name,
            fingerprint=updated.fingerprint,
            version=updated.version,
            status=updated.status,
        )

    def retire(self, experiment_id: int) -> ExperimentOutcome:
        """Retire an experiment (EXP-001)."""
        return self.update(experiment_id, status="retired")

    def add_run(
        self,
        experiment_id: int,
        *,
        run_label: str,
        engine_type: str,
        engine_snapshot_id: int,
        notes: str | None = None,
    ) -> RunOutcome:
        """Associate an engine snapshot with an experiment (EXP-003)."""
        store = ExpSnapshotStore(self._session)
        experiment = store.get(experiment_id)
        if experiment is None:
            raise ExperimentNotFoundError(f"experiment {experiment_id} not found")

        # Check if experiment is active
        if experiment.status != "active":
            raise ExperimentRetiredError("can only add runs to active experiments")

        # Validate engine_type
        if engine_type not in ENGINE_TABLES:
            raise ValidationError(f"invalid engine_type: {engine_type}")

        # Validate snapshot exists and type matches
        engine_fingerprint = self._validate_snapshot(engine_type, engine_snapshot_id)

        # Create run
        run = ExpRun(
            experiment_id=experiment_id,
            run_label=run_label,
            engine_type=engine_type,
            engine_snapshot_id=engine_snapshot_id,
            engine_fingerprint=engine_fingerprint,
            notes=notes,
        )
        self._session.add(run)
        self._session.flush()  # populate run.id
        self._session.commit()

        return RunOutcome(
            run_id=run.id,
            experiment_id=experiment_id,
            run_label=run_label,
            engine_type=engine_type,
            engine_snapshot_id=engine_snapshot_id,
            engine_fingerprint=engine_fingerprint,
            notes=notes,
        )

    def list_experiments(
        self,
        lottery_id: int,
        *,
        status: str | None = None,
    ) -> list[ExperimentEntry]:
        """List experiments for a lottery (EXP-004)."""
        self._resolve_lottery(lottery_id)
        store = ExpSnapshotStore(self._session)
        experiments = store.list_by_lottery(lottery_id, status=status)
        return [
            ExperimentEntry(
                experiment_id=e.id,
                lottery_id=e.lottery_id,
                name=e.name,
                description=e.description,
                fingerprint=e.fingerprint,
                version=e.version,
                status=e.status,
                config_json=e.config_json,
                created_at=e.created_at.isoformat(),
            )
            for e in experiments
        ]

    # --- Comparison (EXP-005) ---

    def compare(
        self,
        experiment_id: int,
        *,
        run_ids: list[int],
    ) -> ComparisonOutcome:
        """Compare runs within an experiment (EXP-005).

        Reads metrics from referenced engine tables, builds a sorted
        comparison matrix, and persists it as an immutable JSON snapshot.
        Idempotent: same (experiment_id, run_ids) returns cached result.
        """
        store = ExpSnapshotStore(self._session)
        experiment = store.get(experiment_id)
        if experiment is None:
            raise ExperimentNotFoundError(f"experiment {experiment_id} not found")

        if len(run_ids) < 2:
            raise ComparisonInsufficientRunsError(f"at least 2 runs required, got {len(run_ids)}")

        # Check for cached comparison (idempotent)
        sorted_ids = sorted(run_ids)
        existing = self._find_cached_comparison(experiment_id, sorted_ids)
        if existing is not None:
            return ComparisonOutcome(
                comparison_id=existing.id,
                experiment_id=experiment_id,
                comparison_json=existing.comparison_json,
                created_at=existing.created_at.isoformat(),
            )

        # Fetch ExpRun rows for each run_id
        stmt = select(ExpRun).where(
            ExpRun.experiment_id == experiment_id,
            ExpRun.id.in_(run_ids),
        )
        runs = list(self._session.execute(stmt).scalars().all())

        if len(runs) != len(run_ids):
            missing = set(run_ids) - {r.id for r in runs}
            raise ExpSnapshotNotFoundError(f"runs not found: {missing}")

        # Build comparison matrix — query engine result tables for metrics
        run_entries = []
        all_metric_names: set[str] = set()

        for run in sorted(runs, key=lambda r: r.run_label):
            metrics = self._read_run_metrics(run)
            all_metric_names.update(metrics.keys())
            run_entries.append(
                {
                    "run_id": run.id,
                    "run_label": run.run_label,
                    "engine_type": run.engine_type,
                    "engine_snapshot_id": run.engine_snapshot_id,
                    "metrics": metrics,
                }
            )

        comparison_data = {
            "experiment_id": experiment_id,
            "runs": run_entries,
            "metric_names": sorted(all_metric_names),
            "created_at": datetime.now(UTC).isoformat(),
        }

        import json

        comparison_json = json.dumps(comparison_data, default=str)

        # Persist immutable comparison snapshot
        comparison = ExpComparison(
            experiment_id=experiment_id,
            comparison_json=comparison_json,
        )
        self._session.add(comparison)
        self._session.flush()
        self._session.commit()

        return ComparisonOutcome(
            comparison_id=comparison.id,
            experiment_id=experiment_id,
            comparison_json=comparison_json,
            created_at=comparison.created_at.isoformat(),
        )

    def _find_cached_comparison(
        self, experiment_id: int, sorted_run_ids: list[int]
    ) -> ExpComparison | None:
        """Check for an existing comparison with the same run_ids (idempotent)."""
        import json

        stmt = select(ExpComparison).where(
            ExpComparison.experiment_id == experiment_id,
        )
        for comp in self._session.execute(stmt).scalars().all():
            data = json.loads(comp.comparison_json)
            existing_ids = sorted(r["run_id"] for r in data["runs"])
            if existing_ids == sorted_run_ids:
                return comp
        return None

    def _read_run_metrics(self, run: ExpRun) -> dict[str, float]:
        """Read metrics from the referenced engine result table."""
        if run.engine_type == "backtesting":
            return self._read_bt_metrics(run.engine_snapshot_id)
        elif run.engine_type == "ml":
            return self._read_ml_metrics(run.engine_snapshot_id)
        elif run.engine_type == "dl":
            return self._read_dl_metrics(run.engine_snapshot_id)
        elif run.engine_type == "optimization":
            return self._read_opt_metrics(run.engine_snapshot_id)
        return {}

    def _read_bt_metrics(self, snapshot_id: int) -> dict[str, float]:
        """Read aggregate_metrics_json from bt_results."""
        import json

        from backend.app.models.bt_result import BtResult

        stmt = select(BtResult).where(BtResult.snapshot_id == snapshot_id)
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return {}
        data = json.loads(result.aggregate_metrics_json)
        # Normalize all values to float
        return {k: float(v) for k, v in data.items()}

    def _read_ml_metrics(self, snapshot_id: int) -> dict[str, float]:
        """Read metrics from ml_metrics rows, building a dict by metric_name."""
        from backend.app.models.ml_metric import MlMetric

        stmt = select(MlMetric).where(MlMetric.snapshot_id == snapshot_id)
        rows = self._session.execute(stmt).scalars().all()
        metrics: dict[str, float] = {}
        for row in rows:
            # Use metric_name as key; if duplicate, average them
            key = row.metric_name
            val = float(row.value)
            if key in metrics:
                metrics[key] = (metrics[key] + val) / 2
            else:
                metrics[key] = val
        return metrics

    def _read_dl_metrics(self, snapshot_id: int) -> dict[str, float]:
        """Read metrics from dl_metrics rows, building a dict by metric_name."""
        from backend.app.models.dl_metric import DlMetric

        stmt = select(DlMetric).where(DlMetric.snapshot_id == snapshot_id)
        rows = self._session.execute(stmt).scalars().all()
        metrics: dict[str, float] = {}
        for row in rows:
            key = row.metric_name
            val = float(row.value)
            if key in metrics:
                metrics[key] = (metrics[key] + val) / 2
            else:
                metrics[key] = val
        return metrics

    def _read_opt_metrics(self, snapshot_id: int) -> dict[str, float]:
        """Read metrics from opt_results rows, building a dict by target_model."""
        from backend.app.models.opt_result import OptResult

        stmt = select(OptResult).where(OptResult.snapshot_id == snapshot_id)
        rows = self._session.execute(stmt).scalars().all()
        metrics: dict[str, float] = {}
        for row in rows:
            metrics[f"best_fitness_{row.target_model}"] = float(row.best_fitness)
        return metrics

    # --- Export (EXP-006) ---

    def export(self, experiment_id: int, *, format: str) -> str:
        """Export experiment data in JSON or CSV format (EXP-006)."""
        if format not in ("json", "csv"):
            raise ExportFormatInvalidError(f"unsupported format: {format}")

        store = ExpSnapshotStore(self._session)
        experiment = store.get(experiment_id)
        if experiment is None:
            raise ExperimentNotFoundError(f"experiment {experiment_id} not found")

        # Fetch runs
        stmt = select(ExpRun).where(ExpRun.experiment_id == experiment_id)
        runs = list(self._session.execute(stmt).scalars().all())

        # Fetch comparisons
        comp_stmt = select(ExpComparison).where(ExpComparison.experiment_id == experiment_id)
        comparisons = list(self._session.execute(comp_stmt).scalars().all())

        run_dicts = [
            {
                "run_id": r.id,
                "run_label": r.run_label,
                "engine_type": r.engine_type,
                "engine_snapshot_id": r.engine_snapshot_id,
                "engine_fingerprint": r.engine_fingerprint,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]

        comp_dicts = [
            {
                "comparison_id": c.id,
                "experiment_id": c.experiment_id,
                "comparison_json": c.comparison_json,
                "created_at": c.created_at.isoformat(),
            }
            for c in comparisons
        ]

        experiment_dict = {
            "experiment_id": experiment.id,
            "lottery_id": experiment.lottery_id,
            "name": experiment.name,
            "description": experiment.description,
            "fingerprint": experiment.fingerprint,
            "version": experiment.version,
            "status": experiment.status,
            "config_json": experiment.config_json,
            "created_at": experiment.created_at.isoformat(),
        }

        if format == "json":
            data = {
                "experiment": experiment_dict,
                "runs": run_dicts,
                "comparisons": comp_dicts,
            }
            return ExperimentExporter.export_json(data)
        else:
            return ExperimentExporter.export_csv(run_dicts)

    def _resolve_lottery(self, lottery_id: int) -> None:
        """Validate lottery exists."""
        from backend.app.models.lottery import Lottery

        if self._session.get(Lottery, lottery_id) is None:
            raise NotFoundError(f"lottery {lottery_id} does not exist")

    def _check_duplicate_name(self, lottery_id: int, name: str, current_fingerprint: str) -> None:
        """Check for duplicate name within lottery (different fingerprint)."""
        stmt = select(ExpExperiment).where(
            ExpExperiment.lottery_id == lottery_id,
            ExpExperiment.name == name,
            ExpExperiment.status == "active",
        )
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing is not None and existing.fingerprint != current_fingerprint:
            raise DuplicateExperimentError(f"experiment with name '{name}' already exists")

    def _validate_snapshot(self, engine_type: str, snapshot_id: int) -> str:
        """Validate snapshot exists and return its fingerprint."""
        # Import the engine model dynamically based on engine_type
        if engine_type == "backtesting":
            from backend.app.models.bt_snapshot import BtSnapshot

            model = BtSnapshot
        elif engine_type == "ml":
            from backend.app.models.ml_snapshot import MlSnapshot

            model = MlSnapshot
        elif engine_type == "dl":
            from backend.app.models.dl_snapshot import DlSnapshot

            model = DlSnapshot
        elif engine_type == "optimization":
            from backend.app.models.opt_snapshot import OptSnapshot

            model = OptSnapshot
        else:
            raise ValidationError(f"invalid engine_type: {engine_type}")

        snapshot = self._session.get(model, snapshot_id)
        if snapshot is None:
            raise ExpSnapshotNotFoundError(f"snapshot {snapshot_id} not found")

        # Return the fingerprint from the snapshot
        return snapshot.fingerprint
