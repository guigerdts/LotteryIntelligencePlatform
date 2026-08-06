"""API v1 router: health and version endpoints wrapped in the standard envelope."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config.settings import get_settings
from backend.app.schemas.envelope import SuccessEnvelope

api_v1_router = APIRouter()


@api_v1_router.get("/health", response_model=SuccessEnvelope[dict[str, str]], tags=["system"])
def health() -> SuccessEnvelope[dict[str, str]]:
    """Return a liveness probe confirming the API is up."""
    return SuccessEnvelope(data={"status": "ok"})


@api_v1_router.get("/version", response_model=SuccessEnvelope[dict[str, str]], tags=["system"])
def version() -> SuccessEnvelope[dict[str, str]]:
    """Return the running application name and version from settings."""
    settings = get_settings()
    return SuccessEnvelope(data={"version": settings.app_version, "app": settings.app_name})
