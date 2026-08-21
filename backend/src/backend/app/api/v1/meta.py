"""Meta Learning API router (META-013).

4 endpoints: POST /meta/rank, GET /meta/ranking, POST /meta/select, GET /meta/selection.
Standard envelope {success, data|error, timestamp}.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.meta import (
    RankingResult,
    RankingSnapshot,
    RankRequest,
    SelectionResult,
    SelectionSnapshot,
    SelectRequest,
)
from backend.app.services.meta_service import MetaService

router = APIRouter(prefix="/meta", tags=["meta"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/rank",
    response_model=SuccessEnvelope[RankingResult],
    summary="Compute a ranking for a lottery (META-005)",
)
def rank(body: RankRequest, db: DbSession) -> SuccessEnvelope[RankingResult]:
    """Compute a ranking for the given lottery using weighted scoring."""
    result = MetaService(db).rank(
        lottery_id=body.lottery_id,
        engine_types=body.engine_types,
        weights=body.weights,
    )
    return SuccessEnvelope(
        data=RankingResult(
            ranking_id=result.ranking_id,
            lottery_id=result.lottery_id,
            context_hash=result.context_hash,
            version=result.version,
            status=result.status,
            fingerprint=result.fingerprint,
            entries=result.entries,
        )
    )


@router.get(
    "/ranking",
    response_model=SuccessEnvelope[RankingSnapshot],
    summary="Retrieve ranking snapshot (META-010)",
)
def get_ranking(
    lottery_id: int,
    db: DbSession,
    context_hash: str | None = Query(default=None, description="Filter by context hash"),
) -> SuccessEnvelope[RankingSnapshot]:
    """Retrieve ranking snapshot for a lottery, optionally filtered by context hash."""
    result = MetaService(db).get_ranking(lottery_id, context_hash=context_hash)
    return SuccessEnvelope(
        data=RankingSnapshot(
            lottery_id=result.lottery_id,
            context_hash=result.context_hash,
            rankings=result.rankings,
        )
    )


@router.post(
    "/select",
    response_model=SuccessEnvelope[SelectionResult],
    summary="Compute a selection from the active ranking (META-006)",
)
def select(body: SelectRequest, db: DbSession) -> SuccessEnvelope[SelectionResult]:
    """Compute a selection from the active ranking for the given lottery."""
    result = MetaService(db).select(
        lottery_id=body.lottery_id,
        top_k=body.top_k,
        min_score=body.min_score,
    )
    return SuccessEnvelope(
        data=SelectionResult(
            selection_id=result.selection_id,
            lottery_id=result.lottery_id,
            ranking_id=result.ranking_id,
            context_hash=result.context_hash,
            version=result.version,
            status=result.status,
            fingerprint=result.fingerprint,
            entries=result.entries,
        )
    )


@router.get(
    "/selection",
    response_model=SuccessEnvelope[SelectionSnapshot],
    summary="Retrieve selection snapshot (META-010)",
)
def get_selection(
    lottery_id: int,
    db: DbSession,
    context_hash: str | None = Query(default=None, description="Filter by context hash"),
) -> SuccessEnvelope[SelectionSnapshot]:
    """Retrieve selection snapshot for a lottery, optionally filtered by context hash."""
    result = MetaService(db).get_selection(lottery_id, context_hash=context_hash)
    return SuccessEnvelope(
        data=SelectionSnapshot(
            lottery_id=result.lottery_id,
            context_hash=result.context_hash,
            selections=result.selections,
        )
    )
