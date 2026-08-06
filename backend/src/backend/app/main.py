"""FastAPI application factory: wires the Fase 0 backend foundation together.

Bootstrap responsibility only — logging, engine, CORS, routing, and a global
error boundary. No business/engine logic and no schema/table creation (Fase 1
migrations own ``Base.metadata.create_all``). Exposes ``create_app`` for both
``uvicorn backend.app.main:create_app`` and the test suite.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.errors import register_domain_error_handlers
from backend.app.api.v1.router import api_v1_router
from backend.app.config.settings import get_settings
from backend.app.core.db import init_db
from backend.app.core.logging import configure_logging
from backend.app.repositories.base import engine
from backend.app.schemas.envelope import ErrorDetail, ErrorEnvelope

logger = getLogger("backend.app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: ensure DB file, log level and engine readiness.

    ``init_db`` creates the local SQLite file (and its parent directory) on
    first startup when it does not exist — no schema or tables, those belong to
    Fase 1 migrations. Emitting the startup line through the structured format
    exercises the logging seam.
    """
    settings = get_settings()
    init_db(settings.database_url)
    logger.info(
        "Fase 0 backend starting (app=%s, version=%s)", settings.app_name, settings.app_version
    )
    logger.info("Database engine ready: %s", engine.url)
    yield
    logger.info("Fase 0 backend stopped")


def create_app() -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = get_settings()
    configure_logging(settings.logging_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    _register_error_handlers(app)
    register_domain_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    """Map every failure path onto the standard error envelope."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        envelope = ErrorEnvelope(error=ErrorDetail(code="http_error", message=str(exc.detail)))
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def starlette_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        envelope = ErrorEnvelope(error=ErrorDetail(code="http_error", message=str(exc.detail)))
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        envelope = ErrorEnvelope(
            error=ErrorDetail(code="validation_error", message=str(exc.errors()))
        )
        return JSONResponse(status_code=422, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error serving %s", request.url.path)
        envelope = ErrorEnvelope(
            error=ErrorDetail(code="internal_error", message="Internal server error")
        )
        return JSONResponse(status_code=500, content=envelope.model_dump())
