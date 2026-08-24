"""Numbers pipeline API router: one endpoint (R1/R3/D10).

Mirrors ``api/v1/gen.py``: parse the request, delegate to
:class:`backend.app.services.pipeline_service.PipelineService`, wrap the
outcome in the standard envelope. A failed stage surfaces as
``PIPE_STAGE_FAILED`` mapped to HTTP 502 by the global domain-error handler.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.pipeline import PipelineRunRequest, PipelineRunResult
from backend.app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/numbers",
    response_model=SuccessEnvelope[PipelineRunResult],
    summary="Run the canonical numbers chain and return the per-stage report",
)
def run_numbers(payload: PipelineRunRequest, db: DbSession) -> SuccessEnvelope[PipelineRunResult]:
    """Heal-and-run stats→features→ml→dl→bt→rank→select→gen in one call (R1).

    Missing/stale prerequisites are repaired by running exactly the deficient
    stages (R2); every response carries the ordered eight-stage report (R3);
    unchanged inputs reuse stored fingerprints with zero side effects (R4).
    """
    outcome = PipelineService(db).run(
        lottery_id=payload.lottery_id,
        count=payload.count,
        seed=payload.seed,
    )
    return SuccessEnvelope(data=PipelineRunResult.model_validate(outcome))
