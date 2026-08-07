"""API error-mapping tests (PR-4, P4-04; User Req 5).

Each row of the design Error Taxonomy is proven: the shared domain handler maps
the error's own envelope ``code`` to the mandated HTTP status. Direct handler
invocation covers the domain errors that F1 endpoints cannot raise through the
HTTP path (e.g. service ValidationError and DatasetLockedError — no draw-create
or dataset endpoint exists in F1); the endpoints that CAN raise them are covered
end-to-end in the CRUD test files. The generic 500 path is proven with a forced
unexpected exception and asserts no traceback leaks.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.api.errors import domain_error_handler
from backend.app.main import create_app
from backend.app.repositories.errors import DuplicateError, ReferentialError
from backend.app.services.errors import (
    DatasetLockedError,
    FeatureDefinitionError,
    GenerationError,
    ImportConflictError,
    ImportStateConflictError,
    NotFoundError,
    SnapshotLockedError,
    SnapshotNotFoundError,
    SoftDeletedError,
    ValidationError,
)

# --- domain handler mapping (design Error Taxonomy, one row per error) ------


def _run_handler(exc: Exception) -> tuple[int, dict]:
    response = domain_error_handler(request=None, exc=exc)
    return response.status_code, json.loads(response.body)


def test_validation_error_maps_to_422() -> None:
    status, body = _run_handler(ValidationError("out of range"))

    assert status == 422
    assert body["success"] is False
    assert body["error"] == {"code": "validation_error", "message": "out of range"}
    assert body["timestamp"]


def test_duplicate_error_maps_to_409() -> None:
    status, body = _run_handler(DuplicateError("duplicate lottery code"))

    assert status == 409
    assert body["error"]["code"] == "DUPLICATE_RESOURCE"


def test_referential_error_maps_to_409() -> None:
    status, body = _run_handler(ReferentialError("row is referenced"))

    assert status == 409
    assert body["error"]["code"] == "REFERENTIAL_CONSTRAINT"


def test_dataset_locked_error_maps_to_409() -> None:
    status, body = _run_handler(DatasetLockedError("dataset is immutable"))

    assert status == 409
    assert body["error"]["code"] == "DATASET_LOCKED"


def test_not_found_error_maps_to_404() -> None:
    status, body = _run_handler(NotFoundError("draw 999 does not exist"))

    assert status == 404
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_soft_deleted_error_maps_to_410_user_mandate() -> None:
    """User mandate overrides design: RESOURCE_SOFT_DELETED -> 410 Gone, not 404."""
    status, body = _run_handler(SoftDeletedError("draw 1 is soft-deleted"))

    assert status == 410
    assert body["error"]["code"] == "RESOURCE_SOFT_DELETED"


def test_import_conflict_error_maps_to_409() -> None:
    status, body = _run_handler(ImportConflictError("lottery already has an active run"))

    assert status == 409
    assert body["error"]["code"] == "IMPORT_CONFLICT"


def test_import_state_conflict_error_maps_to_409() -> None:
    status, body = _run_handler(ImportStateConflictError("illegal state transition"))

    assert status == 409
    assert body["error"]["code"] == "IMPORT_STATE_CONFLICT"


# --- F4 feature-engine channel (P2-01) ---------------------------------------


def test_feature_definition_error_maps_to_500() -> None:
    """A broken feature registry definition is a 500 definition_error (P2-01)."""
    status, body = _run_handler(FeatureDefinitionError("cycle: {a, b}"))

    assert status == 500
    assert body["error"]["code"] == "definition_error"


def test_generation_error_maps_to_500() -> None:
    """An unrecoverable feature generation failure maps to 500 generation_error."""
    status, body = _run_handler(GenerationError("feature generation failed"))

    assert status == 500
    assert body["error"]["code"] == "generation_error"


def test_snapshot_not_found_error_maps_to_404() -> None:
    """A missing feature snapshot read maps to 404 SNAPSHOT_NOT_FOUND."""
    status, body = _run_handler(SnapshotNotFoundError("no feature snapshot"))

    assert status == 404
    assert body["error"]["code"] == "SNAPSHOT_NOT_FOUND"


def test_snapshot_locked_error_maps_to_409() -> None:
    """In-place mutation of a locked feature snapshot maps to 409 SNAPSHOT_LOCKED."""
    status, body = _run_handler(SnapshotLockedError("snapshot is immutable"))

    assert status == 409
    assert body["error"]["code"] == "SNAPSHOT_LOCKED"


# --- unexpected errors never expose stack traces -----------------------------


def test_unexpected_error_returns_500_without_stack_trace() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret-internal-detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "internal_error"
    # The envelope message must be the fixed string; no exception detail leaks.
    assert body["error"]["message"] == "Internal server error"
    assert "secret-internal-detail" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
