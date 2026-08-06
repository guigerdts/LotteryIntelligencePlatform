"""Service-layer domain errors carrying project envelope codes (PR-3, scope item 3).

Domain services raise these for application-owned business and policy failures,
and pass repository errors (:class:`backend.app.repositories.errors.DuplicateError`
/ ``ReferentialError``) through unchanged — those already carry their envelope
codes. Every error exposed by a service exposes a ``code`` attribute that PR-4
maps to the API envelope + HTTP status.

Fase 0 codes (``validation_error``, ``http_error``, ``internal_error``) are kept
intact and reused where the taxonomy already defines them; the new codes added
by F1 follow the uppercase API_SPEC style (DUPLICATE_RESOURCE,
REFERENTIAL_CONSTRAINT, DATASET_LOCKED, RESOURCE_SOFT_DELETED,
RESOURCE_NOT_FOUND).
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for service-layer domain errors (typed business failures)."""

    code: str = "RESOURCE_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ValidationError(ServiceError):
    """A service-owned invariant (CD-06) was violated. Envelope ``validation_error`` (422)."""

    code = "validation_error"


class NotFoundError(ServiceError):
    """A requested resource does not exist. Envelope ``RESOURCE_NOT_FOUND`` (404)."""

    code = "RESOURCE_NOT_FOUND"


class DatasetLockedError(ServiceError):
    """A locked, immutable dataset was targeted for mutation. Envelope ``DATASET_LOCKED`` (409)."""

    code = "DATASET_LOCKED"


class SoftDeletedError(ServiceError):
    """Functional access to a soft-deleted draw. Envelope ``RESOURCE_SOFT_DELETED`` (404)."""

    code = "RESOURCE_SOFT_DELETED"
