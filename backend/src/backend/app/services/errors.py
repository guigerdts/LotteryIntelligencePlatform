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
    """Functional access to a soft-deleted draw. Envelope ``RESOURCE_SOFT_DELETED`` (410)."""

    code = "RESOURCE_SOFT_DELETED"


class ImportConflictError(ServiceError):
    """A new import for a lottery was launched while another run is in progress (D-J).

    Envelope ``IMPORT_CONFLICT`` (409). Registered in the API by PR-3 (S3-02).
    """

    code = "IMPORT_CONFLICT"


class ImportStateConflictError(ServiceError):
    """An illegal import state transition was attempted (terminal immutability, D-E).

    Envelope ``IMPORT_STATE_CONFLICT`` (409). Registered in the API by PR-3 (S3-02).
    """

    code = "IMPORT_STATE_CONFLICT"


class GenerationError(ServiceError):
    """A statistics generation run failed during a batch or engine step (design §3).

    Unrecoverable engine/batch failures raise this after the snapshot is marked
    terminal ``failed`` — never ``active``/``partial``. Envelope ``generation_error``
    (500). Registered in the API by PR-3.
    """

    code = "generation_error"


class SnapshotNotFoundError(ServiceError):
    """A statistics snapshot was requested but none exists for the (lottery, metric_set).

    Read paths surface this (STE-10) and MUST NOT auto-precompute. Envelope
    ``SNAPSHOT_NOT_FOUND`` (404). Registered in the API by PR-3.
    """

    code = "SNAPSHOT_NOT_FOUND"


class SnapshotLockedError(ServiceError):
    """An immutable (locked) snapshot was targeted for in-place mutation (design §7).

    Snapshots are never recomputed in place; this is unreachable by design but
    guards the immutability contract. Envelope ``SNAPSHOT_LOCKED`` (409).
    Registered in the API by PR-3.
    """

    code = "SNAPSHOT_LOCKED"


class FeatureDefinitionError(ServiceError):
    """A feature registry definition is invalid (cycle, unknown dep, bad contract) (P2-01).

    Registration fails-fast on a dependency cycle (FES-07, design §6) and the
    service surfaces this as a non-retryable definition failure. Envelope
    ``definition_error`` (500). Distinct from ``GenerationError``: this is a
    definition/registry fault, not a batch/engine runtime failure.
    """

    code = "definition_error"


class InsufficientDataError(ServiceError):
    """Not enough data for the requested operation (OE-08).

    Optimization requires ≥100 real draws. Below that threshold, a clean
    ``INSUFFICIENT_DATA`` (422) response is returned with no opt_* rows written.
    """

    code = "INSUFFICIENT_DATA"


class ExperimentError(ServiceError):
    """Base class for experiment-related errors (EXP-008)."""

    code = "EXPERIMENT_ERROR"


class ExperimentNotFoundError(ExperimentError):
    """Experiment not found."""

    code = "EXPERIMENT_NOT_FOUND"


class ExperimentRetiredError(ExperimentError):
    """Cannot update retired experiment."""

    code = "EXPERIMENT_RETIRED"


class DuplicateExperimentError(ExperimentError):
    """Duplicate experiment name within lottery."""

    code = "DUPLICATE_EXPERIMENT"


class ExpSnapshotNotFoundError(ExperimentError):
    """Engine snapshot not found."""

    code = "SNAPSHOT_NOT_FOUND"


class SnapshotTypeMismatchError(ExperimentError):
    """Engine snapshot type mismatch."""

    code = "SNAPSHOT_TYPE_MISMATCH"


class ExportFormatInvalidError(ExperimentError):
    """Invalid export format."""

    code = "EXPORT_FORMAT_INVALID"


class ComparisonError(ServiceError):
    """Base class for comparison-related errors (EXP-008)."""

    code = "COMPARISON_ERROR"


class ComparisonInsufficientRunsError(ComparisonError):
    """Insufficient runs for comparison."""

    code = "COMPARISON_INSUFFICIENT_RUNS"


class MetaServiceError(ServiceError):
    """Base class for meta-learning service errors (META-016)."""

    code = "META_ERROR"

    # HTTP 404 — resource not found
    META_RANKING_NOT_FOUND = "META_RANKING_NOT_FOUND"
    META_SELECTION_NOT_FOUND = "META_SELECTION_NOT_FOUND"
    META_NO_ENGINE_DATA = "META_NO_ENGINE_DATA"

    # HTTP 422 — validation failure
    META_WEIGHTS_INVALID = "META_WEIGHTS_INVALID"
    META_TOP_K_INVALID = "META_TOP_K_INVALID"

    # HTTP 409 — conflict
    META_DUPLICATE_RANKING = "META_DUPLICATE_RANKING"

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
