"""ExpSnapshotStore — exp_* I/O owner (EXP-001/002/004).

Handles all persistence for ``exp_experiments``, ``exp_runs``, and
``exp_comparisons`` with atomic lifecycle transitions, fingerprint-based
idempotency, and multi-lottery isolation.
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.models.exp_experiment import ExpExperiment


class ExpSnapshotStore:
    """exp_* read/write owner (EXP-001).

    Every write targets ``exp_*`` tables exclusively — no other tables
    are modified. Lifecycle transitions are atomic within a single
    transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, experiment_id: int) -> ExpExperiment | None:
        """Return the experiment by ID, or None."""
        return self._session.get(ExpExperiment, experiment_id)

    def find_by_fingerprint(self, fingerprint: str) -> ExpExperiment | None:
        """Return the active experiment matching *fingerprint* (idempotency)."""
        stmt = select(ExpExperiment).where(
            ExpExperiment.fingerprint == fingerprint,
            ExpExperiment.status == "active",
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def next_version(self, lottery_id: int, name: str) -> str:
        """Return the next monotonic version string for the scope."""
        stmt = select(func.max(ExpExperiment.version)).where(
            ExpExperiment.lottery_id == lottery_id,
            ExpExperiment.name == name,
        )
        result = self._session.execute(stmt).scalar()
        if result is None:
            return "1"
        return str(int(result) + 1)

    def create(
        self,
        *,
        lottery_id: int,
        name: str,
        description: str | None,
        status: str,
        fingerprint: str,
        version: str,
        config_json: str | None = None,
    ) -> ExpExperiment:
        """Create a new experiment row.

        Single transaction: flush to populate ``id``.
        """
        experiment = ExpExperiment(
            lottery_id=lottery_id,
            name=name,
            description=description,
            status=status,
            fingerprint=fingerprint,
            version=version,
            config_json=config_json,
        )
        self._session.add(experiment)
        self._session.flush()  # populate experiment.id
        return experiment

    def update(
        self,
        experiment: ExpExperiment,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        fingerprint: str | None = None,
        version: str | None = None,
        config_json: str | None = None,
    ) -> ExpExperiment:
        """Update mutable fields on an existing experiment.

        Only provided (non-None) fields are changed. Caller must flush/commit.
        """
        if name is not None:
            experiment.name = name
        if description is not None:
            experiment.description = description
        if status is not None:
            experiment.status = status
        if fingerprint is not None:
            experiment.fingerprint = fingerprint
        if version is not None:
            experiment.version = version
        if config_json is not None:
            experiment.config_json = config_json
        self._session.flush()
        return experiment

    def mark_failed(self, experiment_id: int) -> None:
        """Mark an experiment as *failed* on error."""
        stmt = (
            update(ExpExperiment)
            .where(
                ExpExperiment.id == experiment_id,
                ExpExperiment.status == "active",
            )
            .values(status="failed")
        )
        self._session.execute(stmt)

    def list_by_lottery(
        self,
        lottery_id: int,
        *,
        status: str | None = None,
    ) -> list[ExpExperiment]:
        """Return experiments for a lottery, ordered by created_at DESC."""
        stmt = select(ExpExperiment).where(
            ExpExperiment.lottery_id == lottery_id,
        )
        if status is not None:
            stmt = stmt.where(ExpExperiment.status == status)
        stmt = stmt.order_by(ExpExperiment.created_at.desc())
        return list(self._session.execute(stmt).scalars().all())
