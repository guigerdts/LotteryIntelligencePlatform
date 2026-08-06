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
``main.py``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.repositories.errors import RepositoryError
from backend.app.schemas.envelope import ErrorDetail, ErrorEnvelope
from backend.app.services.errors import ServiceError

# Envelope code -> HTTP status (design Error Taxonomy; RESOURCE_SOFT_DELETED is
# 410 per user mandate overriding design's 404).
_CODE_TO_STATUS: dict[str, int] = {
    "validation_error": 422,
    "DUPLICATE_RESOURCE": 409,
    "REFERENTIAL_CONSTRAINT": 409,
    "DATASET_LOCKED": 409,
    "RESOURCE_SOFT_DELETED": 410,
    "RESOURCE_NOT_FOUND": 404,
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
