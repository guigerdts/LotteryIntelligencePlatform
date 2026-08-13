"""Generator API router: 4 endpoints (GEN-010).

Mirrors ``api/v1/meta.py``: each endpoint parses the request, delegates to
``GenService`` and wraps the result in the standard envelope
``{success, data|error, timestamp}`` (REQ-02). Service results are Pydantic
dataclasses mapped onto the response schemas via ``model_validate``
(``from_attributes=True``) — no field-by-field mapping. No SQL and no business
logic live here; every domain failure propagates as a ``GenServiceError`` that
the global handler maps onto the GEN-013 taxonomy (404/409/422).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.gen import (
    CombinationList,
    GenerateRequest,
    GenerationResult,
    SnapshotList,
    SnapshotResult,
    SnapshotUpdateRequest,
)
from backend.app.services.gen_service import GenService

router = APIRouter(prefix="/gen", tags=["generator"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/generate",
    response_model=SuccessEnvelope[GenerationResult],
    summary="Generate (or idempotently return) a lottery combination snapshot",
)
def generate(payload: GenerateRequest, db: DbSession) -> SuccessEnvelope[GenerationResult]:
    """Run the generator pipeline for a lottery; idempotent (GEN-001, GEN-008).

    ``count`` defaults to 10 (GEN-002); ``seed`` and ``selection_id`` are
    optional overrides (GEN-003, GEN-009). A request that reproduces the active
    snapshot exactly returns it instead of writing a new version.
    """
    result = GenService(db).generate(
        lottery_id=payload.lottery_id,
        count=payload.count,
        seed=payload.seed,
        selection_id=payload.selection_id,
    )
    return SuccessEnvelope(data=GenerationResult.model_validate(result))


@router.get(
    "/combinations",
    response_model=SuccessEnvelope[CombinationList],
    summary="Read stored combinations of a generator snapshot (no recompute)",
)
def get_combinations(
    lottery_id: int,
    db: DbSession,
    snapshot_id: Annotated[int | None, Query(description="snapshot filter")] = None,
) -> SuccessEnvelope[CombinationList]:
    """Return stored combinations; the active snapshot when ``snapshot_id`` is omitted."""
    result = GenService(db).get_combinations(lottery_id, snapshot_id=snapshot_id)
    return SuccessEnvelope(data=CombinationList.model_validate(result))


@router.post(
    "/snapshot",
    response_model=SuccessEnvelope[SnapshotResult],
    summary="Transition a generator snapshot lifecycle status (GEN-007)",
)
def update_snapshot(
    payload: SnapshotUpdateRequest, db: DbSession
) -> SuccessEnvelope[SnapshotResult]:
    """Transition a stored snapshot to ``retired`` or ``failed``.

    Requesting ``active`` is rejected with ``GEN_DUPLICATE_SNAPSHOT`` (409).
    """
    result = GenService(db).update_snapshot(
        lottery_id=payload.lottery_id,
        snapshot_id=payload.snapshot_id,
        status=payload.status,
    )
    return SuccessEnvelope(data=SnapshotResult.model_validate(result))


@router.get(
    "/snapshots",
    response_model=SuccessEnvelope[SnapshotList],
    summary="List generator snapshots for a lottery (GEN-010)",
)
def get_snapshots(lottery_id: int, db: DbSession) -> SuccessEnvelope[SnapshotList]:
    """Return all stored generator snapshots for a lottery, by version DESC."""
    result = GenService(db).get_snapshots(lottery_id)
    return SuccessEnvelope(data=SnapshotList.model_validate(result))
