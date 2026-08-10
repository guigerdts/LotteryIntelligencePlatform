"""OptService: composition root for the Optimization Engine (OE-10).

Wires the opt engine to its Provider Protocols and ``OptSnapshotStore``.
Owns the single atomic transaction: create(active) → bulk_insert →
retire_old_active → commit. On failure → rollback + terminal ``failed``.
Manual-only: no auto-retire, no scheduler, no import hooks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.opt.engine import ObjectiveConfig, run_optimization
from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.registry import get_optimizer_defaults
from backend.app.opt.search_space import SearchSpace
from backend.app.opt.snapshot_store import OptSnapshotStore
from backend.app.services.errors import InsufficientDataError

# OE-08: minimum real draws required for optimization.
MIN_DRAWS: int = 100


@dataclass(frozen=True)
class TrainOutcome:
    """Result of one optimization run within the service."""

    optimizer: str
    lottery_id: int
    status: str
    fingerprint: str
    snapshot_id: int | None = None
    best_fitness: float | None = None
    n_evaluations: int | None = None
    error: str | None = None


class OptService:
    """Composition root for opt — one atomic tx per optimization run (OE-10)."""

    def __init__(
        self,
        session: Session,
        objective_fn: callable,
        search_space: SearchSpace,
        *,
        lottery_id: int,
        optimizer: str,
        metric: str = "f1",
        direction: str = "maximize",
        seed: int = 42,
        version: str = "1.0.0",
        draw_count: int = 0,
        termination: TerminationConfig | None = None,
    ) -> None:
        self._session = session
        self._objective_fn = objective_fn
        self._search_space = search_space
        self._lottery_id = lottery_id
        self._optimizer = optimizer
        self._metric = metric
        self._direction = direction
        self._seed = seed
        self._version = version
        self._draw_count = draw_count
        self._termination = termination or TerminationConfig(
            termination="fixed", max_evaluations=50
        )

    def train(self) -> TrainOutcome:
        """Run one optimization pass within one atomic transaction."""
        # OE-08: data floor check — reject if <100 draws.
        if self._draw_count < MIN_DRAWS:
            raise InsufficientDataError(
                f"optimization requires ≥{MIN_DRAWS} real draws; "
                f"lottery {self._lottery_id} has {self._draw_count}"
            )

        store = OptSnapshotStore(self._session)
        version = store.next_version(self._lottery_id, self._optimizer)

        # Create header (status=active initially, retired on commit).
        header = store.create_snapshot(
            lottery_id=self._lottery_id,
            optimizer=self._optimizer,
            model_set="core-4",
            objective_metric=self._metric,
            objective_direction=self._direction,
            algorithm_params=json.dumps(get_optimizer_defaults(self._optimizer), sort_keys=True),
            search_space=json.dumps({}, sort_keys=True),
            termination=self._termination.termination,
            termination_params=json.dumps(
                {
                    "max_evaluations": self._termination.max_evaluations,
                    "patience": self._termination.patience,
                },
                sort_keys=True,
            ),
            fingerprint="",  # filled after optimization
            version=version,
            status="active",
            is_locked=True,
            draw_count=0,
        )

        try:
            result = run_optimization(
                optimizer_slug=self._optimizer,
                objective_fn=self._objective_fn,
                search_space=self._search_space,
                seed=self._seed,
                termination=self._termination,
                objective_config=ObjectiveConfig(metric=self._metric, direction=self._direction),
                version=self._version,
            )

            # Update header with computed values.
            header.fingerprint = f"opt-{self._optimizer}-{version}"

            # Retire old, commit — one atomic tx.
            store.retire_old_active(self._lottery_id, self._optimizer, keep_id=header.id)
            self._session.commit()

            return TrainOutcome(
                optimizer=self._optimizer,
                lottery_id=self._lottery_id,
                status="active",
                fingerprint=header.fingerprint,
                snapshot_id=header.id,
                best_fitness=float(result.best_fitness),
                n_evaluations=result.n_evaluations,
            )

        except Exception as exc:
            self._session.rollback()
            store.mark_failed(header.id)
            self._session.commit()
            return TrainOutcome(
                optimizer=self._optimizer,
                lottery_id=self._lottery_id,
                status="failed",
                fingerprint="",
                snapshot_id=header.id,
                error=str(exc),
            )

    def get_active_snapshot(self) -> dict | None:
        """Return the active opt snapshot metadata for a lottery, or None."""
        store = OptSnapshotStore(self._session)
        snapshot = store.get_active(self._lottery_id, self._optimizer)
        if snapshot is None:
            return None
        return {
            "id": snapshot.id,
            "lottery_id": snapshot.lottery_id,
            "optimizer": snapshot.optimizer,
            "model_set": snapshot.model_set,
            "version": snapshot.version,
            "status": snapshot.status,
            "fingerprint": snapshot.fingerprint,
            "objective_metric": snapshot.objective_metric,
            "objective_direction": snapshot.objective_direction,
        }

    def get_results(self) -> list[dict]:
        """Return persisted results for the active snapshot."""
        store = OptSnapshotStore(self._session)
        snapshot = store.get_active(self._lottery_id, self._optimizer)
        if snapshot is None:
            return []
        rows = store.results_for_snapshot(snapshot.id)
        return [
            {
                "target_model": r.target_model,
                "fitness": float(r.fitness),
                "params_json": r.params_json,
                "convergence_json": r.convergence_json,
            }
            for r in rows
        ]


__all__ = ["OptService", "TrainOutcome"]
