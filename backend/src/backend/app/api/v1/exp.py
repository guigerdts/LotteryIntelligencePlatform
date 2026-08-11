"""Experiment API router (EXP-001/003/004/005/006).

Provides endpoints for experiment CRUD, run association, listing,
comparison, and export.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.exp_service import ExpService

router = APIRouter(prefix="/experiment", tags=["experiment"])
DbSession = Annotated[Session, Depends(get_db)]


# --- Pydantic v2 schemas (EXP-008) ---


class ExperimentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lottery_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    config_json: str | None = Field(default=None, max_length=10000)


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    experiment_id: int
    lottery_id: int
    name: str
    description: str | None
    fingerprint: str
    version: str
    status: str
    config_json: str | None
    created_at: str


class ExperimentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|retired|failed)$")
    config_json: str | None = Field(default=None, max_length=10000)


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_label: str = Field(min_length=1, max_length=100)
    engine_type: str = Field(pattern="^(backtesting|ml|dl|optimization)$")
    engine_snapshot_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=1000)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    run_id: int
    experiment_id: int
    run_label: str
    engine_type: str
    engine_snapshot_id: int
    engine_fingerprint: str
    notes: str | None


# --- Endpoints ---


@router.post(
    "/create",
    response_model=SuccessEnvelope[ExperimentResponse],
    summary="Create a new experiment",
)
def create_experiment(
    body: ExperimentCreateRequest, db: DbSession
) -> SuccessEnvelope[ExperimentResponse]:
    service = ExpService(db)
    outcome = service.create(
        lottery_id=body.lottery_id,
        name=body.name,
        description=body.description,
        config_json=body.config_json,
    )
    return SuccessEnvelope(
        data=ExperimentResponse(
            experiment_id=outcome.experiment_id,
            lottery_id=outcome.lottery_id,
            name=outcome.name,
            fingerprint=outcome.fingerprint,
            version=outcome.version,
            status=outcome.status,
            description=None,
            config_json=None,
            created_at="",
        )
    )


@router.get(
    "/{experiment_id}",
    response_model=SuccessEnvelope[ExperimentResponse],
    summary="Get experiment by ID",
)
def get_experiment(experiment_id: int, db: DbSession) -> SuccessEnvelope[ExperimentResponse]:
    service = ExpService(db)
    entry = service.get(experiment_id)
    return SuccessEnvelope(
        data=ExperimentResponse(
            experiment_id=entry.experiment_id,
            lottery_id=entry.lottery_id,
            name=entry.name,
            description=entry.description,
            fingerprint=entry.fingerprint,
            version=entry.version,
            status=entry.status,
            config_json=entry.config_json,
            created_at=entry.created_at,
        )
    )


@router.patch(
    "/{experiment_id}",
    response_model=SuccessEnvelope[ExperimentResponse],
    summary="Update experiment fields",
)
def update_experiment(
    experiment_id: int,
    body: ExperimentUpdateRequest,
    db: DbSession,
) -> SuccessEnvelope[ExperimentResponse]:
    service = ExpService(db)
    outcome = service.update(
        experiment_id,
        name=body.name,
        description=body.description,
        status=body.status,
        config_json=body.config_json,
    )
    return SuccessEnvelope(
        data=ExperimentResponse(
            experiment_id=outcome.experiment_id,
            lottery_id=outcome.lottery_id,
            name=outcome.name,
            fingerprint=outcome.fingerprint,
            version=outcome.version,
            status=outcome.status,
            description=None,
            config_json=None,
            created_at="",
        )
    )


@router.get(
    "/",
    response_model=SuccessEnvelope[list[ExperimentResponse]],
    summary="List experiments for a lottery",
)
def list_experiments(
    lottery_id: int,
    db: DbSession,
    status: str | None = Query(default=None, pattern="^(active|retired|failed)$"),
) -> SuccessEnvelope[list[ExperimentResponse]]:
    service = ExpService(db)
    entries = service.list_experiments(lottery_id, status=status)
    return SuccessEnvelope(
        data=[
            ExperimentResponse(
                experiment_id=e.experiment_id,
                lottery_id=e.lottery_id,
                name=e.name,
                description=e.description,
                fingerprint=e.fingerprint,
                version=e.version,
                status=e.status,
                config_json=e.config_json,
                created_at=e.created_at,
            )
            for e in entries
        ]
    )


@router.post(
    "/{experiment_id}/run",
    response_model=SuccessEnvelope[RunResponse],
    summary="Associate an engine snapshot with an experiment",
)
def add_run(
    experiment_id: int,
    body: RunCreateRequest,
    db: DbSession,
) -> SuccessEnvelope[RunResponse]:
    service = ExpService(db)
    outcome = service.add_run(
        experiment_id,
        run_label=body.run_label,
        engine_type=body.engine_type,
        engine_snapshot_id=body.engine_snapshot_id,
        notes=body.notes,
    )
    return SuccessEnvelope(
        data=RunResponse(
            run_id=outcome.run_id,
            experiment_id=outcome.experiment_id,
            run_label=outcome.run_label,
            engine_type=outcome.engine_type,
            engine_snapshot_id=outcome.engine_snapshot_id,
            engine_fingerprint=outcome.engine_fingerprint,
            notes=outcome.notes,
        )
    )


# --- Comparison (EXP-005) ---


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_ids: list[int] = Field(min_length=2)


class ComparisonRunEntry(BaseModel):
    run_id: int
    run_label: str
    engine_type: str
    engine_snapshot_id: int
    metrics: dict[str, float]


class ComparisonResponse(BaseModel):
    comparison_id: int
    experiment_id: int
    runs: list[ComparisonRunEntry]
    metric_names: list[str]
    created_at: str


@router.post(
    "/{experiment_id}/compare",
    response_model=SuccessEnvelope[ComparisonResponse],
    summary="Compare runs within an experiment",
)
def compare_runs(
    experiment_id: int,
    body: ComparisonRequest,
    db: DbSession,
) -> SuccessEnvelope[ComparisonResponse]:
    import json

    service = ExpService(db)
    outcome = service.compare(experiment_id, run_ids=body.run_ids)
    data = json.loads(outcome.comparison_json)
    return SuccessEnvelope(
        data=ComparisonResponse(
            comparison_id=outcome.comparison_id,
            experiment_id=data["experiment_id"],
            runs=[ComparisonRunEntry(**r) for r in data["runs"]],
            metric_names=data["metric_names"],
            created_at=data["created_at"],
        )
    )


# --- Export (EXP-006) ---


@router.get(
    "/{experiment_id}/export",
    summary="Export experiment results as JSON or CSV",
)
def export_experiment(
    experiment_id: int,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: DbSession = None,
) -> Response:
    service = ExpService(db)
    content = service.export(experiment_id, format=format)
    if format == "csv":
        return Response(content=content, media_type="text/csv")
    return Response(content=content, media_type="application/json")
