"""AI assistant API router (F15, A-06..A-12): 5 envelope-wrapped endpoints.

Thin delegates over ``AiService``; errors map via the domain handler (404
RESOURCE_NOT_FOUND/EXPERIMENT_NOT_FOUND, 422 scope/body, 500 ``assistant_error``).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.assistant import AssistantResponse, AssistRequest, SummarizeRequest
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.ai_service import AiService

router = APIRouter(prefix="/assistant", tags=["assistant"])
DbSession = Annotated[Session, Depends(get_db)]

ReportScope = Literal["frequency", "gap", "average", "probability", "experiment"]


def _envelope(result) -> SuccessEnvelope[AssistantResponse]:
    """Wrap a ``GenerationResult`` in the standard assistant envelope (A-12)."""
    return SuccessEnvelope(
        data=AssistantResponse(
            text=result.text,
            engine_version=result.engine_version,
            fingerprint=result.fingerprint,
        )
    )


@router.get(
    "/explain",
    response_model=SuccessEnvelope[AssistantResponse],
    summary="Explain a lottery's results in Spanish",
)
def explain(
    lottery_code: str,
    db: DbSession,
    subject: Annotated[str | None, Query()] = None,
    context: Annotated[str | None, Query()] = None,
) -> SuccessEnvelope[AssistantResponse]:
    """Spanish explanation of the active snapshot (frequencies/gaps/averages)."""
    return _envelope(AiService(db).explain(lottery_code=lottery_code))


@router.get(
    "/interpret",
    response_model=SuccessEnvelope[AssistantResponse],
    summary="Interpret the chart data in Spanish",
)
def interpret(lottery_code: str, db: DbSession) -> SuccessEnvelope[AssistantResponse]:
    """Spanish interpretation of the data behind the client-side charts (D6)."""
    return _envelope(AiService(db).interpret(lottery_code=lottery_code))


@router.get(
    "/report",
    response_model=SuccessEnvelope[AssistantResponse],
    summary="Render a scoped Spanish plain-text report",
)
def report(
    lottery_code: str,
    db: DbSession,
    scope: Annotated[ReportScope | None, Query()] = None,
) -> SuccessEnvelope[AssistantResponse]:
    """Structured markdown-ish report; unsupported ``scope`` is a 422."""
    return _envelope(AiService(db).report(lottery_code=lottery_code, scope=scope))


@router.post(
    "/summarize",
    response_model=SuccessEnvelope[AssistantResponse],
    summary="Summarize an experiment comparison in Spanish",
)
def summarize(payload: SummarizeRequest, db: DbSession) -> SuccessEnvelope[AssistantResponse]:
    """Spanish summary of ``exp.compare()`` data; no comparison -> empty text."""
    return _envelope(
        AiService(db).summarize(experiment_id=payload.experiment_id, run_ids=payload.run_ids)
    )


@router.post(
    "/assist",
    response_model=SuccessEnvelope[AssistantResponse],
    summary="Route a free-text question to the matching generator",
)
def assist(payload: AssistRequest, db: DbSession) -> SuccessEnvelope[AssistantResponse]:
    """Classify the question by intent; unknown intents get capabilities text."""
    return _envelope(
        AiService(db).assist(question=payload.question, lottery_code=payload.lottery_code)
    )
