"""ExpService — experiment service layer (EXP-001/002/003/004).

Exposes experiment CRUD and run association through a service boundary.
API and CLI call this layer; the service owns DB access, validation,
and persistence via ``ExpSnapshotStore``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.experiments.fingerprint import compute_exp_fingerprint
from backend.app.experiments.snapshot_store import ExpSnapshotStore
from backend.app.models.exp_experiment import ExpExperiment
from backend.app.models.exp_run import ExpRun
from backend.app.services.errors import (
    DuplicateExperimentError,
    ExperimentNotFoundError,
    ExperimentRetiredError,
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
