"""DL API router: train + snapshot/metric reads (REQ-10/11 dl paragraphs, DLE-14).

Manual-only write: ``POST /dl/train`` is the ONLY write path. Reads are served
from stored snapshots only — they never train (DLE-14). All responses use the
standard envelope. NO ``/dl/predict``, ranking, or weights-download endpoints:
the dl routes are limited to train/models/metrics (REQ-11).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.api.v1.etag import etag_for, should_not_modify
from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.dl_service import DlService, DlTrainOutcome
from backend.app.services.errors import NotFoundError, SnapshotNotFoundError

router = APIRouter(prefix="/dl", tags=["dl"])

DbSession = Annotated[Session, Depends(get_db)]

# Registry insertion order IS the canonical training order (mlp→lstm).
_DL_FAMILY_ORDER: tuple[str, ...] = ("mlp", "lstm")


def _train_rows(outcome: DlTrainOutcome) -> list[dict]:
    """Project one model-set run outcome onto per-family result rows.

    A DL run trains mlp→lstm under ONE snapshot, so both rows carry the same
    run-level outcome — the shape mirrors the ML train response per family.
    """
    return [
        {
            "family": family,
            "status": outcome.status,
            "snapshot_id": outcome.snapshot_id,
            "fingerprint": outcome.fingerprint,
            "metrics_checksum": outcome.metrics_checksum,
            "error": outcome.error,
        }
        for family in _DL_FAMILY_ORDER
    ]


@router.post(
    "/train",
    response_model=SuccessEnvelope[dict],
    summary="Train the core-3 DL families for a lottery",
)
def train_models(
    lottery_id: int,
    db: DbSession,
    model_set: str = "core-3",
    window: int = 10,
    cut: int | None = None,
) -> SuccessEnvelope[dict]:
    """Trigger DL training on demand; manual-only, no scheduler.

    Resolves lottery by id (unknown → 404 ``RESOURCE_NOT_FOUND``). One atomic
    transaction covers both families; an omitted ``cut`` defaults to the
    walk-forward boundary (``len(frame)*4//5``).
    """
    _resolve_lottery(db, lottery_id)

    service = _build_service(db)
    outcome = service.train(lottery_id, model_set, window=window, cut=cut)

    return SuccessEnvelope(data={"lottery_id": lottery_id, "results": _train_rows(outcome)})


@router.get(
    "/models",
    response_model=SuccessEnvelope[dict],
    summary="Get active DL snapshot metadata for a lottery",
)
def get_models(
    lottery_id: int,
    db: DbSession,
) -> SuccessEnvelope[dict]:
    """Return the active DL snapshot for a lottery, or 404 if none exists."""
    _resolve_lottery(db, lottery_id)

    service = _build_service(db)
    result = service.get_active_snapshot(lottery_id)

    if result is None:
        raise SnapshotNotFoundError(f"no active DL snapshot for lottery {lottery_id}")

    return SuccessEnvelope(data=result)


@router.get(
    "/metrics",
    response_model=SuccessEnvelope[list[dict]],
    summary="Get DL metrics for the active snapshot",
)
def get_metrics(
    lottery_id: int,
    db: DbSession,
    request: Request,
    response: Response,
    model_id: str | None = None,
) -> SuccessEnvelope[list[dict]]:
    """Return persisted DL metrics for the active snapshot.

    Matching ``If-None-Match`` → ``304`` empty body (REQ-13 parity).
    """
    _resolve_lottery(db, lottery_id)

    service = _build_service(db)
    snapshot = service.get_active_snapshot(lottery_id)
    if snapshot is not None:
        etag = etag_for(snapshot)
        if should_not_modify(request.headers, etag):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        response.headers["ETag"] = etag
    metrics = service.get_metrics(lottery_id, model_id=model_id)

    return SuccessEnvelope(data=metrics)


def _resolve_lottery(db: Session, lottery_id: int) -> None:
    """Resolve a lottery id; raise 404 when unknown."""
    lottery = db.get(LotteryRepository.model, lottery_id)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_id} does not exist")


def _build_service(db: Session) -> DlService:
    """Compose a per-request DlService over fresh adapters (per-request instances)."""
    return DlService(db, _DrawAdapter(db), _FeatureAdapter(db))


class _DrawAdapter:
    """Minimal DL DrawHistoryProvider adapter reading from the draw repository."""

    def __init__(self, session: Session) -> None:
        """Store the session used for read-only draw queries."""
        self._session = session

    def iter_draws(self, lottery_id: int, *, after_draw_number: int | None = None):
        """Yield ``DrawRow`` carriers in ascending draw-number order."""
        from sqlalchemy import select

        from backend.app.dl.providers import DrawRow
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
            yield DrawRow(draw_number=draw.draw_number, numbers=numbers)


class _FeatureAdapter:
    """Minimal DL FeatureSnapshotProvider adapter reading from feature_values."""

    def __init__(self, session: Session) -> None:
        """Store the session used for read-only feature queries."""
        self._session = session

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        """Return the newest active ML snapshot id for the lottery, if any."""
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
        """Yield ``FeatureRow`` carriers ordered by draw then feature."""
        from sqlalchemy import select

        from backend.app.dl.providers import FeatureRow
        from backend.app.models.feature_value import FeatureValue

        stmt = (
            select(FeatureValue)
            .where(FeatureValue.snapshot_id == snapshot_id)
            .order_by(FeatureValue.draw_number, FeatureValue.feature_id)
        )
        for fv in self._session.execute(stmt).scalars().all():
            yield FeatureRow(
                feature_id=fv.feature_id,
                draw_number=fv.draw_number,
                value=float(fv.value),
            )
