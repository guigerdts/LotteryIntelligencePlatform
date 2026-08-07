"""API v1 router: system endpoints plus the Fase 1 CRUD routers (CD-07).

Mounts the lotteries, draws, statistics and feature-engine routers alongside the
Fase 0 health/version endpoints. Every endpoint shares the standard envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.draws import router as draws_router
from backend.app.api.v1.feature_engine import router as feature_engine_router
from backend.app.api.v1.lotteries import router as lotteries_router
from backend.app.api.v1.statistics import router as statistics_router
from backend.app.config.settings import get_settings
from backend.app.schemas.envelope import SuccessEnvelope

api_v1_router = APIRouter()
api_v1_router.include_router(lotteries_router)
api_v1_router.include_router(draws_router)
api_v1_router.include_router(statistics_router)
api_v1_router.include_router(feature_engine_router)


@api_v1_router.get("/health", response_model=SuccessEnvelope[dict[str, str]], tags=["system"])
def health() -> SuccessEnvelope[dict[str, str]]:
    """Return a liveness probe confirming the API is up."""
    return SuccessEnvelope(data={"status": "ok"})


@api_v1_router.get("/version", response_model=SuccessEnvelope[dict[str, str]], tags=["system"])
def version() -> SuccessEnvelope[dict[str, str]]:
    """Return the running application name and version from settings."""
    settings = get_settings()
    return SuccessEnvelope(data={"version": settings.app_version, "app": settings.app_name})
