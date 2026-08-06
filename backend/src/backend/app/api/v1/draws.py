"""Draws API router: functional reads per API_SPEC §4 subset (CD-07).

Fase 1 exposes only GET endpoints for draws — ``/draws/latest``, ``/draws/import``
and ``/draws/upload`` are Fase 2 (CD-07, design scope item 4) and are therefore
NOT mounted. Draws are created only through the domain service (import/F2
pipeline), never through the API in F1. List supports pagination, ``?lottery=<code>``
lookup and ``date_from``/``date_to`` filters (API_SPEC §19); every response uses
the Fase 0 envelope (REQ-02). The repository eagerly loads children, so the
serialization never lazy-loads in loops (design, scope item 8).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.draw import DrawRead
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.draw_service import DrawService

router = APIRouter(prefix="/draws", tags=["draws"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=SuccessEnvelope[list[DrawRead]])
def list_draws(
    db: DbSession,
    lottery: Annotated[str | None, Query(description="Lottery code filter")] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    order: Annotated[Literal["asc", "desc"], Query()] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SuccessEnvelope[list[DrawRead]]:
    """List draws, filtered/ordered/paginated, soft-deleted rows always excluded."""
    draws = DrawService(db).list_draws(
        lottery_code=lottery,
        date_from=date_from,
        date_to=date_to,
        order=order,
        page=page,
        page_size=page_size,
    )
    return SuccessEnvelope(data=[DrawRead.model_validate(d) for d in draws])


@router.get("/{draw_id}", response_model=SuccessEnvelope[DrawRead])
def get_draw(draw_id: int, db: DbSession) -> SuccessEnvelope[DrawRead]:
    """Get one draw with its nested numbers + super number.

    Absent rows surface RESOURCE_NOT_FOUND (404); explicit access to a
    soft-deleted draw surfaces RESOURCE_SOFT_DELETED (410 Gone per user mandate).
    """
    draw = DrawService(db).get_draw(draw_id)
    return SuccessEnvelope(data=DrawRead.model_validate(draw))
