"""Optimization schemas — request/response models for /opt endpoints.

Pydantic v2 models matching design §8 and backend delta REQ-10/11/12.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OptTrainRequest(BaseModel):
    """Request body for POST /opt/train."""

    lottery_id: int = Field(..., description="Lottery ID to optimize for")
    optimizer: str = Field(
        default="ga",
        description="Optimizer slug: ga, pso, bayesian, or sa",
    )
    metric: str = Field(
        default="f1",
        description="Objective metric: f1, roc_auc, accuracy, precision, or recall",
    )
    direction: str = Field(
        default="maximize",
        description="Optimization direction: maximize or minimize",
    )
    seed: int = Field(default=42, description="RNG seed for reproducibility")


class OptTrainOutcome(BaseModel):
    """One optimization run outcome."""

    optimizer: str
    lottery_id: int
    status: str
    fingerprint: str
    snapshot_id: int | None = None
    best_fitness: float | None = None
    n_evaluations: int | None = None
    error: str | None = None


class OptSnapshotRead(BaseModel):
    """Active opt snapshot metadata."""

    id: int
    lottery_id: int
    optimizer: str
    model_set: str
    version: str
    status: str
    fingerprint: str
    objective_metric: str
    objective_direction: str


class OptResultRead(BaseModel):
    """One persisted optimization result."""

    target_model: str
    fitness: float
    params_json: str
    convergence_json: str


__all__ = [
    "OptTrainRequest",
    "OptTrainOutcome",
    "OptSnapshotRead",
    "OptResultRead",
]
