"""Domain error -> HTTP envelope mapping (PR-4, scope items 3-4).

Registers FastAPI exception handlers that translate Fase 1 domain errors
(:mod:`backend.app.services.errors` and :mod:`backend.app.repositories.errors`)
onto the standard Fase 0 error envelope (REQ-02) with the HTTP status the design
Error Taxonomy assigns (design, scope item 3; User Req 5).

Every domain error carries a ``code`` attribute; the single handler below derives
both the HTTP status and the envelope code from it, so one registration covers
every typed failure. ``RESOURCE_SOFT_DELETED`` maps to **410 Gone** per explicit
user mandate — the design said 404, the user overrides (deviation documented in
the apply-progress). Fase 0 codes (``http_error``, ``validation_error``,
``internal_error``) are kept unchanged and handled by the existing handlers in
``main.py``. The F2 import channel adds ``IMPORT_CONFLICT`` and
``IMPORT_STATE_CONFLICT`` (both 409) to the taxonomy (IE-21, D-J/D-E).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.repositories.errors import RepositoryError
from backend.app.schemas.envelope import ErrorDetail, ErrorEnvelope
from backend.app.services.errors import ServiceError

# Envelope code -> HTTP status (design Error Taxonomy; RESOURCE_SOFT_DELETED is
# 410 per user mandate overriding design's 404; the F2 import codes are 409).
_CODE_TO_STATUS: dict[str, int] = {
    "validation_error": 422,
    "DUPLICATE_RESOURCE": 409,
    "REFERENTIAL_CONSTRAINT": 409,
    "DATASET_LOCKED": 409,
    "RESOURCE_SOFT_DELETED": 410,
    "RESOURCE_NOT_FOUND": 404,
    # F2 import channel (IE-11): concurrent active run and illegal terminal
    # transition both surface 409 Conflict (D-J, D-E).
    "IMPORT_CONFLICT": 409,
    "IMPORT_STATE_CONFLICT": 409,
    # F3 statistics channel (STE-05/07/§13): unrecoverable generation failure is
    # 500, a missing snapshot read is 404 (never auto-precompute, STE-10), and an
    # in-place mutation of an immutable snapshot is 409 (unreachable by design).
    "generation_error": 500,
    "SNAPSHOT_NOT_FOUND": 404,
    "SNAPSHOT_LOCKED": 409,
    # F4 feature-engine channel (P2-01): a registry/definition fault is a 500
    # ``definition_error``; feature generation reuses the shared ``generation_error``
    # (500) and the snapshot 404/409 rows above already cover feature reads/mutation.
    "definition_error": 500,
    # F10 backtesting channel (BTE-07): insufficient data is 422.
    "INSUFFICIENT_DATA": 422,
    "BT_RUN_ERROR": 500,
}

_UNKNOWN_STATUS = 500


def status_for_code(code: str) -> int:
    """Return the HTTP status for an envelope error code (500 when unknown)."""
    return _CODE_TO_STATUS.get(code, _UNKNOWN_STATUS)


def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap a service/repository domain error in the standard error envelope."""
    code = getattr(exc, "code", "internal_error")
    envelope = ErrorEnvelope(error=ErrorDetail(code=code, message=str(exc)))
    return JSONResponse(status_code=status_for_code(code), content=envelope.model_dump())


def register_domain_error_handlers(app: FastAPI) -> None:
    """Attach the envelope handler to both domain-error base classes."""
    app.add_exception_handler(ServiceError, domain_error_handler)
    app.add_exception_handler(RepositoryError, domain_error_handler)
