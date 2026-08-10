"""Objective function for optimization — wraps ML/DL engines (D5/OE-03).

The objective function is a closure that captures the target engine, data,
and walk-forward split. It evaluates proposed hyperparameters by calling
``ml.engine.train()`` or ``dl.engine.train()`` and returning quantized
Decimal fitness.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Protocol

from backend.app.opt.determinism import quantize_metric

# Supported objective metrics (OE-03).
SUPPORTED_METRICS: Final[frozenset[str]] = frozenset(
    {"f1", "roc_auc", "accuracy", "precision", "recall"}
)
SUPPORTED_DIRECTIONS: Final[frozenset[str]] = frozenset({"maximize", "minimize"})


@dataclass(frozen=True)
class ObjectiveConfig:
    """Configuration for the objective function.

    ``metric`` is the metric to optimize; ``direction`` is maximize/minimize.
    """

    metric: str = "f1"
    direction: str = "maximize"


class ObjectiveFunction(Protocol):
    """Protocol for objective functions used by optimizers."""

    def evaluate(self, params: dict[str, object]) -> Decimal: ...


class MlObjectiveFunction:
    """Objective function wrapping ML engine.

    Evaluates proposed hyperparameters by training an ML model and
    returning the specified metric as quantized Decimal fitness.
    """

    def __init__(
        self,
        family: str,
        lottery_id: int,
        records: list[object],
        snapshot_id: int,
        feature_rows: list[object],
        cut: int | None = None,
        config: ObjectiveConfig | None = None,
    ) -> None:
        self._family = family
        self._lottery_id = lottery_id
        self._records = records
        self._snapshot_id = snapshot_id
        self._feature_rows = feature_rows
        self._cut = cut
        self._config = config or ObjectiveConfig()

    def evaluate(self, params: dict[str, object]) -> Decimal:
        """Evaluate objective with proposed parameters."""
        from backend.app.ml.engine import MlEngine

        engine = MlEngine()
        result = engine.train(
            family=self._family,
            lottery_id=self._lottery_id,
            records=self._records,
            snapshot_id=self._snapshot_id,
            cut=self._cut,
            feature_rows=self._feature_rows,
        )
        fitness = result.metrics.get(self._config.metric, Decimal("0"))
        if self._config.direction == "minimize":
            fitness = -fitness
        return quantize_metric(fitness)


class DlObjectiveFunction:
    """Objective function wrapping DL engine.

    Evaluates proposed hyperparameters by training a DL model and
    returning the specified metric as quantized Decimal fitness.
    """

    def __init__(
        self,
        family: str,
        train_batch: object,
        eval_batch: object,
        config: ObjectiveConfig | None = None,
    ) -> None:
        self._family = family
        self._train_batch = train_batch
        self._eval_batch = eval_batch
        self._config = config or ObjectiveConfig()

    def evaluate(self, params: dict[str, object]) -> Decimal:
        """Evaluate objective with proposed parameters."""
        from backend.app.dl.engine import train

        result = train(
            family=self._family,
            train_batch=self._train_batch,
            eval_batch=self._eval_batch,
            epochs=int(params.get("epochs", 50)),
            batch_size=int(params.get("batch_size", 32)),
            lr=float(params.get("lr", 1e-3)),
        )
        fitness = result.metrics.get(self._config.metric, Decimal("0"))
        if self._config.direction == "minimize":
            fitness = -fitness
        return quantize_metric(fitness)


__all__ = [
    "SUPPORTED_METRICS",
    "SUPPORTED_DIRECTIONS",
    "ObjectiveConfig",
    "ObjectiveFunction",
    "MlObjectiveFunction",
    "DlObjectiveFunction",
]
