"""ExperimentEngine — thin orchestrator for experiment operations (EXP-001).

Delegates to ``ExpSnapshotStore`` and ``ExpService`` for all persistence
and business logic. API and CLI call this layer for high-level operations.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.experiments.snapshot_store import ExpSnapshotStore
from backend.app.services.exp_service import ExpService


class ExperimentEngine:
    """Thin orchestrator for experiment operations (EXP-001).

    Delegates to ExpSnapshotStore and ExpService. This layer provides
    a high-level interface for API and CLI.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._store = ExpSnapshotStore(session)
        self._service = ExpService(session)

    def create_experiment(
        self,
        *,
        lottery_id: int,
        name: str,
        description: str | None = None,
        config_json: str | None = None,
    ):
        """Create a new experiment."""
        return self._service.create(
            lottery_id=lottery_id,
            name=name,
            description=description,
            config_json=config_json,
        )

    def get_experiment(self, experiment_id: int):
        """Get experiment by ID."""
        return self._service.get(experiment_id)

    def update_experiment(
        self,
        experiment_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        config_json: str | None = None,
    ):
        """Update experiment fields."""
        return self._service.update(
            experiment_id,
            name=name,
            description=description,
            status=status,
            config_json=config_json,
        )

    def retire_experiment(self, experiment_id: int):
        """Retire an experiment."""
        return self._service.retire(experiment_id)

    def add_run(
        self,
        experiment_id: int,
        *,
        run_label: str,
        engine_type: str,
        engine_snapshot_id: int,
        notes: str | None = None,
    ):
        """Associate an engine snapshot with an experiment."""
        return self._service.add_run(
            experiment_id,
            run_label=run_label,
            engine_type=engine_type,
            engine_snapshot_id=engine_snapshot_id,
            notes=notes,
        )

    def list_experiments(
        self,
        lottery_id: int,
        *,
        status: str | None = None,
    ):
        """List experiments for a lottery."""
        return self._service.list_experiments(lottery_id, status=status)
