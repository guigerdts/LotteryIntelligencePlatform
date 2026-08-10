"""Optimization engine orchestrator — wraps optimizers (D5/OE-03/OE-04).

Builds the objective function closure, selects optimizer from registry,
runs optimization, and returns TrainResult.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from backend.app.opt.determinism import quantize_metric
from backend.app.opt.fingerprint import compute_opt_fingerprint
from backend.app.opt.optimizer_types import OptimizerProtocol, OptResult, TerminationConfig
from backend.app.opt.registry import build_opt_registry, get_optimizer_defaults
from backend.app.opt.search_space import SearchSpace

logger = logging.getLogger(__name__)

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


def _instantiate_optimizer(slug: str) -> OptimizerProtocol:
    """Instantiate an optimizer by canonical slug (OE-09)."""
    if slug == "ga":
        from backend.app.opt.ga import GaOptimizer

        return GaOptimizer()
    if slug == "pso":
        from backend.app.opt.pso import PsoOptimizer

        return PsoOptimizer()
    if slug == "bayesian":
        from backend.app.opt.bayesian import BayesianOptimizer

        return BayesianOptimizer()
    if slug == "sa":
        from backend.app.opt.sa import SaOptimizer

        return SaOptimizer()
    raise ValueError(f"Unknown optimizer {slug!r}. Known: {sorted(build_opt_registry())}")


def build_objective_function(
    objective_fn: callable,
    config: ObjectiveConfig,
) -> callable:
    """Build the objective function closure for an optimizer.

    Wraps the raw evaluation callable to apply metric selection and
    direction negation, returning quantized Decimal fitness.
    """

    def _evaluate(params: dict[str, object]) -> Decimal:
        fitness = objective_fn(params)
        if config.direction == "minimize":
            fitness = -fitness
        return quantize_metric(fitness)

    return _evaluate


def run_optimization(
    *,
    optimizer_slug: str,
    objective_fn: callable,
    search_space: SearchSpace,
    seed: int,
    termination: TerminationConfig,
    objective_config: ObjectiveConfig | None = None,
    data_hash: str = "",
    version: str = "1.0.0",
) -> OptResult:
    """Run one optimization pass end-to-end.

    1. Instantiate optimizer from registry
    2. Build objective function closure
    3. Compute fingerprint
    4. Run optimization
    5. Return OptResult
    """
    cfg = objective_config or ObjectiveConfig()
    optimizer = _instantiate_optimizer(optimizer_slug)

    wrapped_objective = build_objective_function(objective_fn, cfg)

    compute_opt_fingerprint(
        optimizer=optimizer_slug,
        algorithm_params=get_optimizer_defaults(optimizer_slug),
        objective_metric=cfg.metric,
        objective_direction=cfg.direction,
        search_space={},  # populated by caller
        data_hash=data_hash,
        seed=seed,
        version=version,
        termination_params={},  # populated by caller
    )

    logger.info(
        "Starting optimization: optimizer=%s metric=%s direction=%s seed=%d",
        optimizer_slug,
        cfg.metric,
        cfg.direction,
        seed,
    )

    result = optimizer.optimize(
        objective_fn=wrapped_objective,
        search_space=search_space,
        seed=seed,
        termination=termination,
    )

    logger.info(
        "Optimization complete: best_fitness=%s n_evaluations=%d",
        result.best_fitness,
        result.n_evaluations,
    )

    return result


__all__ = [
    "SUPPORTED_METRICS",
    "SUPPORTED_DIRECTIONS",
    "ObjectiveConfig",
    "_instantiate_optimizer",
    "build_objective_function",
    "run_optimization",
]
