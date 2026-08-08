"""Probability API router: manual generate + stored-value reads (design §7, PES-08).

Strict read/write separation (PES-08): ``POST /probability/generate`` is the ONLY
write path — it is idempotent (an existing active snapshot that reproduces the result
is returned, not duplicated). ``GET /probability/{code}/probabilities`` is a read only
and NEVER precomputes: a missing snapshot surfaces ``SNAPSHOT_NOT_FOUND`` (404) and an
unknown lottery ``RESOURCE_NOT_FOUND`` (404). All responses use the Fase 0 envelope
(REQ-02); the router only parses the request, resolves the lottery code and delegates
to ``ProbabilityService`` — no SQL, no business logic.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.probability.providers import DrawReader, FeatureSnapshotReader, StatSnapshotReader
from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.probability import (
    GenerateRequest,
    GenerateSnapshot,
    ProbRow,
    ProbabilityList,
)
from backend.app.services.errors import NotFoundError
from backend.app.services.probability_service import PROB_MODEL_SET_CORE, ProbabilityService

router = APIRouter(prefix="/probability", tags=["probability"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/generate",
    response_model=SuccessEnvelope[GenerateSnapshot],
    summary="Generate (or idempotently return) a probability snapshot",
)
def generate_snapshot(
    payload: GenerateRequest, db: DbSession, response: Response
) -> SuccessEnvelope[GenerateSnapshot]:
    """Trigger probability snapshot generation on demand; idempotent (design §7).

    Resolves ``lottery_code`` (unknown -> 404 ``RESOURCE_NOT_FOUND``), selects the
    scope and delegates to ``ProbabilityService.generate``. When an ``active``
    snapshot already reproduces the prospective result exactly, the existing snapshot
    is returned with HTTP 200; a new version is written and returned with HTTP 201.
    """
    lottery = _resolve_lottery(db, payload.lottery_code)
    previous = _active_snapshot_id(db, lottery.id, payload.model_set)
    snapshot = ProbabilityService(db).generate(
        lottery_id=lottery.id,
        model_set=payload.model_set,
        scope=payload.scope,
    )
    data = GenerateSnapshot(
        snapshot_id=snapshot.id,
        lottery_code=payload.lottery_code,
        version=snapshot.version,
        model_set=snapshot.model_set,
        prob_generator_version=snapshot.prob_generator_version,
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
    "/{lottery_code}/probabilities",
    response_model=SuccessEnvelope[ProbabilityList],
    summary="Read persisted probabilities from the active snapshot (no precompute)",
)
def read_probabilities(
    lottery_code: str,
    db: DbSession,
    model: Annotated[str | None, Query(description="model_id filter")] = None,
    subject: Annotated[str | None, Query(description="subject filter")] = None,
    last: Annotated[int, Query(ge=0)] = 0,
) -> SuccessEnvelope[ProbabilityList]:
    """Return the persisted probability rows of the active snapshot, bounded by ``last``.

    ``model`` filters to one ``model_id``; ``subject`` filters to one subject;
    ``last=0`` returns everything and ``last>0`` caps the list. Missing snapshot ->
    ``SNAPSHOT_NOT_FOUND`` (404); unknown lottery -> ``RESOURCE_NOT_FOUND`` (404).
    No generation is ever triggered (PES-08).
    """
    snapshot, rows = ProbabilityService(db).read_values(
        lottery_code=lottery_code, model=model, subject=subject, last=last
    )
    return SuccessEnvelope(
        data=ProbabilityList(
            snapshot_id=snapshot.id,
            lottery_code=lottery_code,
            version=snapshot.version,
            prob_generator_version=snapshot.prob_generator_version,
            draws_from=snapshot.draws_from,
            draws_to=snapshot.draws_to,
            draw_count=snapshot.draw_count,
            checksum=snapshot.checksum,
            probabilities=[
                ProbRow(
                    model_id=row.model_id,
                    model_version=row.model_version,
                    subject=row.subject,
                    draw_number=row.draw_number,
                    value=f"{row.value.normalize():f}",
                )
                for row in rows
            ],
        )
    )


def _resolve_lottery(db: Session, lottery_code: str) -> object:
    """Resolve a ``lottery_code`` natural key to its row (404 when unknown)."""
    lottery = LotteryRepository(db).get_by_code(lottery_code)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_code!r} does not exist")
    return lottery


def _active_snapshot_id(db: Session, lottery_id: int, model_set: str) -> int | None:
    """Return the active probability snapshot id for idempotency 200-vs-201 detection."""
    from backend.app.probability.snapshot_store import SnapshotStore

    store = SnapshotStore(db)
    snapshot = store.get_active(lottery_id, model_set)
    return snapshot.id if snapshot is not None else None
