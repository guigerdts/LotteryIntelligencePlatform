"""Optimizer protocol and shared types (OA-01..04).

All optimizers implement ``OptimizerProtocol.optimize()`` which accepts an
objective function, search space, seed, and termination config, returning
an ``OptResult`` with best params, fitness, and convergence history.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from backend.app.opt.convergence import ConvergenceTracker
from backend.app.opt.search_space import SearchSpace


@dataclass(frozen=True)
class TerminationConfig:
    """Termination criteria for an optimizer.

    ``termination`` is either ``fixed`` (run all iterations/generations)
    or ``early_stopping`` (stop when no improvement for ``patience`` evaluations).
    """

    termination: str = "fixed"
    max_generations: int | None = None  # GA, SA
    max_evaluations: int | None = None  # PSO, Bayesian
    patience: int | None = None  # early_stopping only
    min_delta: float = 0.0  # early_stopping only


@dataclass(frozen=True)
class OptResult:
    """Result of one optimization run.

    ``best_params`` is the best found hyperparameter set; ``best_fitness`` is
    the quantized objective value; ``convergence`` is the tracker with full
    evaluation history.
    """

    best_params: dict[str, object]
    best_fitness: Decimal
    convergence: ConvergenceTracker
    n_evaluations: int


class OptimizerProtocol(Protocol):
    """Protocol that all optimizers must implement."""

    def optimize(
        self,
        objective_fn: callable,
        search_space: SearchSpace,
        seed: int,
        termination: TerminationConfig,
    ) -> OptResult: ...


__all__ = ["TerminationConfig", "OptResult", "OptimizerProtocol"]
