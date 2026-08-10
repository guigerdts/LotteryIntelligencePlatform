"""Backtesting API router (BTS-01, BTE-12).

Manual-only surface: ``POST /backtesting/run`` executes on demand.
``GET /backtesting/history`` and ``GET /backtesting/results`` read stored
data.  NO scheduler, NO background jobs (BTE-12).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.repositories.base import get_db
from backend.app.schemas.envelope import SuccessEnvelope
from backend.app.services.bt_service import BtService

router = APIRouter(prefix="/backtesting", tags=["backtesting"])
DbSession = Annotated[Session, Depends(get_db)]


# --- Pydantic v2 schemas (BTS-03) ---


class BtRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lottery_id: int = Field(gt=0)
    strategy_id: str = Field(min_length=1, max_length=100)
    train_years: int = Field(default=5, ge=1, le=50)
    eval_count: int = Field(default=1, ge=1, le=52)
    step_count: int = Field(default=1, ge=1, le=52)
    min_train_draws: int = Field(default=100, ge=10, le=5000)
    seed: int = Field(default=42, ge=0)


class BtRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    snapshot_id: int
    lottery_id: int
    strategy_id: str
    fingerprint: str
    version: str
    status: str


class BtHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    snapshot_id: int
    lottery_id: int
    strategy_id: str
    fingerprint: str
    version: str
    status: str
    created_at: str


class BtMetricsResponse(BaseModel):
    hit_rate: float
    average_matches: float
    consistency_score: float
    total_draws_evaluated: int


class BtWindowResponse(BaseModel):
    window_index: int
    train_range: tuple[int, int]
    eval_range: tuple[int, int]
    strategy_metrics: BtMetricsResponse
    uniform_metrics: BtMetricsResponse | None = None
    hypergeometric_metrics: BtMetricsResponse | None = None


class BtResultResponse(BaseModel):
    snapshot_id: int
    lottery_id: int
    strategy_id: str
    fingerprint: str
    version: str
    status: str
    aggregate_metrics: BtMetricsResponse
    window_history: list[BtWindowResponse]


# --- Endpoints ---


@router.post(
    "/run",
    response_model=SuccessEnvelope[BtRunResponse],
    summary="Execute a backtest on demand (manual-only, BTE-12)",
)
def run_backtest(body: BtRunRequest, db: DbSession) -> SuccessEnvelope[BtRunResponse]:
    outcome = BtService(db).run(
        lottery_id=body.lottery_id,
        strategy_id=body.strategy_id,
        train_years=body.train_years,
        eval_count=body.eval_count,
        step_count=body.step_count,
        min_train_draws=body.min_train_draws,
        seed=body.seed,
    )
    return SuccessEnvelope(
        data=BtRunResponse(
            snapshot_id=outcome.snapshot_id,
            lottery_id=outcome.lottery_id,
            strategy_id=outcome.strategy_id,
            fingerprint=outcome.fingerprint,
            version=outcome.version,
            status=outcome.status,
        )
    )


@router.get(
    "/history",
    response_model=SuccessEnvelope[list[BtHistoryEntry]],
    summary="List backtest snapshots for a lottery (read-only)",
)
def get_history(lottery_id: int, db: DbSession) -> SuccessEnvelope[list[BtHistoryEntry]]:
    return SuccessEnvelope(data=BtService(db).history(lottery_id))


@router.get(
    "/results",
    response_model=SuccessEnvelope[BtResultResponse],
    summary="Get detailed backtest results (read-only)",
)
def get_results(
    lottery_id: int,
    db: DbSession,
    snapshot_id: int | None = Query(default=None, description="Snapshot ID (omit for active)"),
) -> SuccessEnvelope[BtResultResponse]:
    raw = BtService(db).results(lottery_id, snapshot_id=snapshot_id)
    agg = BtMetricsResponse(**raw["aggregate_metrics"])
    windows = [
        BtWindowResponse(
            window_index=w["window_index"],
            train_range=tuple(w["train_range"]),
            eval_range=tuple(w["eval_range"]),
            strategy_metrics=agg,
        )
        for w in raw.get("window_history", [])
    ]
    return SuccessEnvelope(
        data=BtResultResponse(
            snapshot_id=raw["snapshot_id"],
            lottery_id=raw["lottery_id"],
            strategy_id=raw["strategy_id"],
            fingerprint=raw["fingerprint"],
            version=raw["version"],
            status=raw["status"],
            aggregate_metrics=agg,
            window_history=windows,
        )
    )
