"""Standard response envelope schemas shared by every API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with a ``Z`` suffix."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class ErrorDetail(BaseModel):
    """Machine-readable error code plus a human-readable message."""

    code: str
    message: str


class SuccessEnvelope[T](BaseModel):
    """Successful response: ``{success, data, timestamp}``."""

    success: bool = True
    data: T
    timestamp: str = Field(default_factory=utc_now_iso)


class ErrorEnvelope(BaseModel):
    """Error response: ``{success, error, timestamp}``."""

    success: bool = False
    error: ErrorDetail
    timestamp: str = Field(default_factory=utc_now_iso)
