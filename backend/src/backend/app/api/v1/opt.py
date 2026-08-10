"""Opt API router: train + snapshot/result reads (Fase 9, OE-10).

Manual-only write: ``POST /opt/train`` is the ONLY write path. Reads served
from stored snapshots only, never precompute. All responses use the standard
envelope (REQ-02). NO ``/opt/predict`` or ``/opt/rank`` endpoints.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.errors import NotFoundError, SnapshotNotFoundError

router = APIRouter(prefix="/opt", tags=["opt"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/train",
    response_model=SuccessEnvelope[dict],
    summary="Run one optimization pass for a lottery",
)
def train_optimizer(
    lottery_id: int,
    db: DbSession,
    optimizer: str = "ga",
    metric: str = "f1",
    direction: str = "maximize",
    seed: int = 42,
) -> SuccessEnvelope[dict]:
    """Trigger opt training on demand; manual-only, no scheduler.

    Resolves lottery by id (unknown → 404 ``RESOURCE_NOT_FOUND``).
    Returns training outcome with status, fingerprint, and fitness.
    """
    _resolve_lottery(db, lottery_id)

    from backend.app.opt.search_space import SearchParam, SearchSpace
    from backend.app.services.opt_service import OptService

    # Default search space for hyperparameter optimization.
    search_space = SearchSpace(
        params=(
            SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),
            SearchParam(name="n_estimators", param_type="integer", low=10, high=200),
        )
    )

    def dummy_objective(params: dict) -> float:
        """Placeholder objective — returns 0.5 for testing."""
        return 0.5

    service = OptService(
        session=db,
        objective_fn=dummy_objective,
        search_space=search_space,
        lottery_id=lottery_id,
        optimizer=optimizer,
        metric=metric,
        direction=direction,
        seed=seed,
    )
    outcome = service.train()

    return SuccessEnvelope(
        data={
            "lottery_id": lottery_id,
            "optimizer": outcome.optimizer,
            "status": outcome.status,
            "snapshot_id": outcome.snapshot_id,
            "fingerprint": outcome.fingerprint,
            "best_fitness": outcome.best_fitness,
            "n_evaluations": outcome.n_evaluations,
            "error": outcome.error,
        }
    )


@router.get(
    "/models",
    response_model=SuccessEnvelope[dict],
    summary="Get active opt snapshot metadata for a lottery",
)
def get_models(
    lottery_id: int,
    db: DbSession,
    optimizer: str = "ga",
) -> SuccessEnvelope[dict]:
    """Return the active opt snapshot for a lottery, or 404 if none exists."""
    _resolve_lottery(db, lottery_id)

    # Use a dummy objective and search space for reads.
    from backend.app.opt.search_space import SearchParam, SearchSpace
    from backend.app.services.opt_service import OptService

    search_space = SearchSpace(
        params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
    )

    service = OptService(
        session=db,
        objective_fn=lambda p: 0.5,
        search_space=search_space,
        lottery_id=lottery_id,
        optimizer=optimizer,
    )
    result = service.get_active_snapshot()

    if result is None:
        raise SnapshotNotFoundError(f"no active opt snapshot for lottery {lottery_id}")

    return SuccessEnvelope(data=result)


@router.get(
    "/metrics",
    response_model=SuccessEnvelope[list[dict]],
    summary="Get opt results for the active snapshot",
)
def get_metrics(
    lottery_id: int,
    db: DbSession,
    optimizer: str = "ga",
) -> SuccessEnvelope[list[dict]]:
    """Return persisted opt results for the active snapshot."""
    _resolve_lottery(db, lottery_id)

    from backend.app.opt.search_space import SearchParam, SearchSpace
    from backend.app.services.opt_service import OptService

    search_space = SearchSpace(
        params=(SearchParam(name="lr", param_type="continuous", low=1e-5, high=1e-1),)
    )

    service = OptService(
        session=db,
        objective_fn=lambda p: 0.5,
        search_space=search_space,
        lottery_id=lottery_id,
        optimizer=optimizer,
    )
    results = service.get_results()

    return SuccessEnvelope(data=results)


@router.get(
    "/params",
    response_model=SuccessEnvelope[dict],
    summary="Get default params for an optimizer",
)
def get_params(
    optimizer: str = "ga",
) -> SuccessEnvelope[dict]:
    """Return default algorithm params for the requested optimizer."""
    from backend.app.opt.registry import get_optimizer_defaults

    try:
        params = get_optimizer_defaults(optimizer)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc

    return SuccessEnvelope(data={"optimizer": optimizer, "params": params})


def _resolve_lottery(db: Session, lottery_id: int) -> None:
    """Resolve a lottery id; raise 404 when unknown."""
    lottery = db.get(LotteryRepository.model, lottery_id)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_id} does not exist")
