"""Lotteries API router: GET/POST/PUT/DELETE per API_SPEC §3 (CD-07).

Thin HTTP layer only — validates the payload with Pydantic at the boundary,
delegates the use case to :class:`backend.app.services.lottery_service.LotteryService`
and wraps the result in the Fase 0 envelope (REQ-02). No SQL, no business logic,
no direct repository access (design, scope item 4). Domain errors raised by the
service (NotFoundError, DuplicateError, ReferentialError) are mapped by the
global handlers in :mod:`backend.app.api.errors`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.schemas.lottery import LotteryCreate, LotteryRead, LotteryUpdate
from backend.app.services.lottery_service import LotteryService

router = APIRouter(prefix="/lotteries", tags=["lotteries"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=SuccessEnvelope[list[LotteryRead]])
def list_lotteries(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SuccessEnvelope[list[LotteryRead]]:
    """List lotteries, paginated and ordered by id, inside the success envelope."""
    lotteries = LotteryService(db).list(page=page, page_size=page_size)
    return SuccessEnvelope(data=[LotteryRead.model_validate(item) for item in lotteries])


@router.get("/{lottery_id}", response_model=SuccessEnvelope[LotteryRead])
def get_lottery(lottery_id: int, db: DbSession) -> SuccessEnvelope[LotteryRead]:
    """Get one lottery by id; absent rows surface RESOURCE_NOT_FOUND (404)."""
    lottery = LotteryService(db).get(lottery_id)
    return SuccessEnvelope(data=LotteryRead.model_validate(lottery))


@router.post("", response_model=SuccessEnvelope[LotteryRead], status_code=status.HTTP_201_CREATED)
def create_lottery(payload: LotteryCreate, db: DbSession) -> SuccessEnvelope[LotteryRead]:
    """Create a lottery; a duplicate ``code`` surfaces DUPLICATE_RESOURCE (409)."""
    lottery = LotteryService(db).create(payload.model_dump())
    return SuccessEnvelope(data=LotteryRead.model_validate(lottery))


@router.put("/{lottery_id}", response_model=SuccessEnvelope[LotteryRead])
def update_lottery(
    lottery_id: int, payload: LotteryUpdate, db: DbSession
) -> SuccessEnvelope[LotteryRead]:
    """Update mutable lottery fields; ``code`` stays immutable (natural key)."""
    lottery = LotteryService(db).update(lottery_id, payload.model_dump(exclude_unset=True))
    return SuccessEnvelope(data=LotteryRead.model_validate(lottery))


@router.delete("/{lottery_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lottery(lottery_id: int, db: DbSession) -> Response:
    """Delete a lottery; FK RESTRICT with existing draws surfaces 409 (CD-05)."""
    LotteryService(db).delete(lottery_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
