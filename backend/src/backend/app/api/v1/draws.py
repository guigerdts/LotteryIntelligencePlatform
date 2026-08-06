"""Draws API router: functional reads plus the F2 import surface (CD-07, IE-11).

Fase 1 exposes GET reads for draws (list + get by id); ``/draws/latest`` stays
unmounted. Fase 2 adds the two import endpoints (CD-07 scope item 4) —
``POST /draws/import`` (JSON body referencing a server-side ``source_file``) and
``POST /draws/upload`` (multipart CSV streamed to a temp file). Both SHALL force
``import_type="manual"`` server-side and SHALL never read ``import_type`` from
the client (D-C/IE-11); the router only resolves the lottery code, delegates to
``ImportService.run_import`` and wraps the audit summary in the standard envelope
(REQ-02). Draws are created only through the domain pipeline — no draw mutation
endpoints exist here.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.schemas.draw import DrawRead
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import NotFoundError
from backend.app.services.import_service import ImportService

_CHUNK_SIZE = 1024 * 1024


class ImportDrawsRequest(BaseModel):
    """JSON body for ``POST /draws/import`` (unknown fields rejected, IE-11/D-C).

    Only a server-side ``source_file`` path is accepted here — the file is never
    uploaded through this endpoint. ``resume`` is optional and defaults to False;
    ``import_type`` is derived by the server (always ``manual``), never read from
    the client.
    """

    model_config = ConfigDict(extra="forbid")

    lottery_code: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    resume: bool = False

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


@router.post(
    "/import",
    response_model=SuccessEnvelope[dict],
    summary="Import draw history from a server-side source path",
)
def import_draws(payload: ImportDrawsRequest, db: DbSession) -> SuccessEnvelope[dict]:
    """Run an import from a ``source_file`` the server can read (IE-11/D-C).

    Resolves ``lottery_code`` to the lottery row (unknown code → 404
    ``RESOURCE_NOT_FOUND``), then delegates to ``ImportService.run_import`` with
    ``import_type`` forced to ``manual``. The audit summary is wrapped in the
    standard envelope. Phase A failure / bad file maps to 422 ``validation_error``;
    a concurrent active run for the same lottery maps to 409 ``IMPORT_CONFLICT``.
    """
    lottery = _resolve_lottery(db, payload.lottery_code)
    summary = ImportService(db).run_import(
        lottery_id=lottery.id,
        source_path=payload.source_file,
        import_type="manual",
        resume=payload.resume,
    )
    return SuccessEnvelope(data=summary)


@router.post(
    "/upload",
    response_model=SuccessEnvelope[dict],
    summary="Import draw history from an uploaded CSV file",
)
def upload_draws(
    db: DbSession,
    lottery_code: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    resume: Annotated[bool, Form()] = False,
) -> SuccessEnvelope[dict]:
    """Run an import from a multipart CSV ``file`` (IE-21/D-C).

    The upload is streamed to a temp file (bounded memory) and passed to
    ``ImportService.run_import``, which itself computes the file SHA-256 — the
    checksum is never re-derived here. ``import_type`` is forced to ``"manual"``
    regardless of any client hint. The temp file is removed after the run.
    """
    lottery = _resolve_lottery(db, lottery_code)
    tmp_path = _stream_upload_to_temp(file)
    try:
        summary = ImportService(db).run_import(
            lottery_id=lottery.id,
            source_path=tmp_path,
            import_type="manual",
            resume=resume,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return SuccessEnvelope(data=summary)


@router.get("/{draw_id}", response_model=SuccessEnvelope[DrawRead])
def get_draw(draw_id: int, db: DbSession) -> SuccessEnvelope[DrawRead]:
    """Get one draw with its nested numbers + super number.

    Absent rows surface RESOURCE_NOT_FOUND (404); explicit access to a
    soft-deleted draw surfaces RESOURCE_SOFT_DELETED (410 Gone per user mandate).
    """
    draw = DrawService(db).get_draw(draw_id)
    return SuccessEnvelope(data=DrawRead.model_validate(draw))


def _resolve_lottery(db: Session, lottery_code: str):
    """Resolve a ``lottery_code`` natural key to its row (404 when unknown, CD-07).

    Routers resolve the code and call the service — no business logic lives here.
    """
    lottery = LotteryRepository(db).get_by_code(lottery_code)
    if lottery is None:
        raise NotFoundError(f"lottery {lottery_code!r} does not exist")
    return lottery


def _stream_upload_to_temp(file: UploadFile) -> Path:
    """Stream an uploaded CSV to a temp file, then return its path.

    ImportService computes the SHA-256 while re-streaming, so no checksum is
    derived here (single source of truth for file hashing).
    """
    fd, path = tempfile.mkstemp(prefix="lip_upload_", suffix=".csv")
    try:
        with os.fdopen(fd, "wb") as handle:
            while chunk := file.file.read(_CHUNK_SIZE):
                handle.write(chunk)
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise
    return Path(path)
