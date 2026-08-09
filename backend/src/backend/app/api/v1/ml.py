"""ML API router: train + model/metric reads (Fase 7, MLE-08, backend delta REQ-10/11/12).

Manual-only write: ``POST /ml/train`` is the ONLY write path. Reads served
from stored snapshots only, never precompute. All responses use the standard
envelope (REQ-02). NO ``/ml/predict`` or ``/ml/ranking`` endpoints.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.errors import NotFoundError, SnapshotNotFoundError
from backend.app.services.ml_service import MlService

router = APIRouter(prefix="/ml", tags=["ml"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/train",
    response_model=SuccessEnvelope[dict],
    summary="Train one or all core-5 ML families for a lottery",
)
def train_models(
    lottery_id: int,
    db: DbSession,
    family: str | None = None,
) -> SuccessEnvelope[dict]:
    """Trigger ML training on demand; manual-only, no scheduler.

    Resolves lottery by id (unknown → 404 ``RESOURCE_NOT_FOUND``).
    When ``family`` is omitted, trains all five core-5 families.
    Returns list of training outcomes with status, fingerprint, and checksum.
    """
    _resolve_lottery(db, lottery_id)

    draw_reader = _DrawAdapter(db)
    feature_provider = _FeatureAdapter(db)

    service = MlService(db, draw_reader, feature_provider)
    outcomes = service.train(lottery_id, family=family)

    return SuccessEnvelope(
        data={
            "lottery_id": lottery_id,
            "results": [
                {
                    "family": o.family,
                    "status": o.status,
                    "snapshot_id": o.snapshot_id,
                    "fingerprint": o.fingerprint,
                    "metrics_checksum": o.metrics_checksum,
                    "error": o.error,
                }
                for o in outcomes
            ],
        }
    )


@router.get(
    "/models",
    response_model=SuccessEnvelope[dict],
    summary="Get active ML snapshot metadata for a lottery",
)
def get_models(
    lottery_id: int,
    db: DbSession,
) -> SuccessEnvelope[dict]:
    """Return the active ML snapshot for a lottery, or 404 if none exists."""
    _resolve_lottery(db, lottery_id)

    draw_reader = _DrawAdapter(db)
    feature_provider = _FeatureAdapter(db)

    service = MlService(db, draw_reader, feature_provider)
    result = service.get_active_snapshot(lottery_id)

    if result is None:
        raise SnapshotNotFoundError(f"no active ML snapshot for lottery {lottery_id}")

    return SuccessEnvelope(data=result)


@router.get(
    "/metrics",
    response_model=SuccessEnvelope[list[dict]],
    summary="Get ML metrics for the active snapshot",
)
def get_metrics(
    lottery_id: int,
    db: DbSession,
    model_id: str | None = None,
) -> SuccessEnvelope[list[dict]]:
    """Return persisted ML metrics for the active snapshot."""
    _resolve_lottery(db, lottery_id)

    draw_reader = _DrawAdapter(db)
    feature_provider = _FeatureAdapter(db)

    service = MlService(db, draw_reader, feature_provider)
    metrics = service.get_metrics(lottery_id, model_id=model_id)

    return SuccessEnvelope(data=metrics)


def _resolve_lottery(db: Session, lottery_id: int) -> None:
    """Resolve a lottery id; raise 404 when unknown."""
    lottery = db.get(LotteryRepository.model, lottery_id)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_id} does not exist")


class _DrawAdapter:
    """Minimal DrawHistoryProvider adapter reading from the draw repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def iter_draws(self, lottery_id: int, *, after_draw_number: int | None = None):
        from sqlalchemy import select

        from backend.app.models.draw import Draw
        from backend.app.models.draw_number import DrawNumber

        stmt = select(Draw).where(Draw.lottery_id == lottery_id).order_by(Draw.draw_number)
        if after_draw_number is not None:
            stmt = stmt.where(Draw.draw_number > after_draw_number)

        for draw in self._session.execute(stmt).scalars().all():
            nums_stmt = (
                select(DrawNumber.number)
                .where(DrawNumber.draw_id == draw.id)
                .order_by(DrawNumber.position)
            )
            numbers = tuple(self._session.execute(nums_stmt).scalars().all())
            from backend.app.ml.providers import DrawRow

            yield DrawRow(draw_number=draw.draw_number, numbers=numbers)


class _FeatureAdapter:
    """Minimal FeatureSnapshotProvider adapter reading from feature_values."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        from sqlalchemy import select

        from backend.app.models.feature_snapshot import FeatureSnapshot

        stmt = (
            select(FeatureSnapshot)
            .where(
                FeatureSnapshot.lottery_id == lottery_id,
                FeatureSnapshot.status == "active",
            )
            .order_by(FeatureSnapshot.version.desc())
            .limit(1)
        )
        snap = self._session.execute(stmt).scalar_one_or_none()
        return snap.id if snap is not None else None

    def feature_rows(self, snapshot_id: int):
        from sqlalchemy import select

        from backend.app.ml.feature_reader import FeatureValueRow
        from backend.app.models.feature_value import FeatureValue

        stmt = (
            select(FeatureValue)
            .where(FeatureValue.snapshot_id == snapshot_id)
            .order_by(FeatureValue.draw_number, FeatureValue.feature_id)
        )
        for fv in self._session.execute(stmt).scalars().all():
            yield FeatureValueRow(
                feature_id=fv.feature_id,
                draw_number=fv.draw_number,
                value=float(fv.value),
            )
