"""Feature-engine API router: manual generate + stored-value reads (design §7, FES-09).

Strict read/write separation (FES-09): ``POST /feature-engine/generate`` is the ONLY
write path — it is idempotent (an existing active snapshot that reproduces the result
is returned, not duplicated). ``GET /feature-engine/{code}/features`` is a read only
and NEVER precomputes: a missing snapshot surfaces ``SNAPSHOT_NOT_FOUND`` (404) and an
unknown lottery ``RESOURCE_NOT_FOUND`` (404) — both via the shared global domain
handler in :mod:`backend.app.api.errors`. All responses use the Fase 0 envelope
(REQ-02); the router only parses the request, resolves the lottery code and delegates
to ``FeatureEngineService`` — no SQL, no business logic (reason mirroring
``api/v1/statistics.py``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.repositories.feature_snapshot_repository import FeatureSnapshotRepository
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.feature_engine import (
    FeatureList,
    FeatureRow,
    GenerateRequest,
    GenerateSnapshot,
)
from backend.app.services.errors import NotFoundError
from backend.app.services.feature_engine_service import FEATURE_SET_CORE, FeatureEngineService

router = APIRouter(prefix="/feature-engine", tags=["feature-engine"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/generate",
    response_model=SuccessEnvelope[GenerateSnapshot],
    summary="Generate (or idempotently return) a feature snapshot",
)
def generate_snapshot(
    payload: GenerateRequest, db: DbSession, response: Response
) -> SuccessEnvelope[GenerateSnapshot]:
    """Trigger feature snapshot generation on demand; idempotent (design §7).

    Resolves ``lottery_code`` (unknown -> 404 ``RESOURCE_NOT_FOUND``), selects the
    scope and delegates to ``FeatureEngineService.generate``. When an ``active``
    snapshot already reproduces the prospective result exactly, the existing snapshot
    is returned with HTTP 200; a new version is written and returned with HTTP 201.
    Registry/engine failure maps to ``definition_error``/``generation_error`` (500).
    """
    lottery = _resolve_lottery(db, payload.lottery_code)
    previous = _active_snapshot_id(db, lottery.id)
    snapshot = FeatureEngineService(db).generate(
        lottery_id=lottery.id,
        feature_set=FEATURE_SET_CORE,
        scope=payload.scope,
    )
    data = GenerateSnapshot(
        snapshot_id=snapshot.id,
        lottery_code=payload.lottery_code,
        version=snapshot.version,
        feature_set=snapshot.feature_set,
        feature_engine_version=snapshot.feature_engine_version,
        draws_from=snapshot.draws_from,
        draws_to=snapshot.draws_to,
        draw_count=snapshot.draw_count,
        checksum=snapshot.checksum,
        incremental=payload.scope == "incremental",
    )
    if snapshot.id != previous:
        response.status_code = status.HTTP_201_CREATED
    return SuccessEnvelope(data=data)


@router.get(
    "/{lottery_code}/features",
    response_model=SuccessEnvelope[FeatureList],
    summary="Read persisted features from the active snapshot (no precompute)",
)
def read_features(
    lottery_code: str,
    db: DbSession,
    feature: Annotated[str | None, Query(description="feature_id filter")] = None,
    last: Annotated[int, Query(ge=0)] = 0,
) -> SuccessEnvelope[FeatureList]:
    """Return the persisted feature rows of the active snapshot, bounded by ``last``.

    ``feature`` filters to one ``feature_id``; ``last=0`` returns everything and
    ``last>0`` caps the list. Missing snapshot -> ``SNAPSHOT_NOT_FOUND`` (404);
    unknown lottery -> ``RESOURCE_NOT_FOUND`` (404). No generation is ever triggered
    (FES-09) — the rows come from the stored ``feature_values`` only.
    """
    snapshot, rows = FeatureEngineService(db).read_features(
        lottery_code=lottery_code, feature=feature, last=last
    )
    return SuccessEnvelope(
        data=FeatureList(
            snapshot_id=snapshot.id,
            lottery_code=lottery_code,
            version=snapshot.version,
            feature_engine_version=snapshot.feature_engine_version,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            draw_count=snapshot.draw_count,
            checksum=snapshot.checksum,
            features=[
                FeatureRow(
                    feature_id=row.feature_id,
                    feature_version=row.feature_version,
                    draw_number=row.draw_number,
                    # Canonical exact form: strip the Numeric(20,8) scale so a stored
                    # ``0E-8`` reads ``"0"`` and ``2.50000000`` reads ``"2.5"`` —
                    # float never enters the wire (FES-05).
                    value=f"{row.value.normalize():f}",
                )
                for row in rows
            ],
        )
    )


def _resolve_lottery(db: Session, lottery_code: str) -> object:
    """Resolve a ``lottery_code`` natural key to its row (404 when unknown, CD-07)."""
    lottery = LotteryRepository(db).get_by_code(lottery_code)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_code!r} does not exist")
    return lottery


def _active_snapshot_id(db: Session, lottery_id: int) -> int | None:
    """Return the active feature snapshot id for idempotency 200-vs-201 detection."""
    snapshot = FeatureSnapshotRepository(db).get_active(lottery_id, FEATURE_SET_CORE)
    return snapshot.id if snapshot is not None else None
