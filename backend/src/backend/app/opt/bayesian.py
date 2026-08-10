"""Bayesian Optimization optimizer using optuna (OA-03).

Uses optuna's TPE sampler to build a probabilistic model of the objective
surface and suggest promising hyperparameters.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from backend.app.opt.convergence import ConvergenceTracker
from backend.app.opt.determinism import quantize_metric
from backend.app.opt.optimizer_types import OptResult, TerminationConfig
from backend.app.opt.search_space import SearchSpace

if TYPE_CHECKING:
    import optuna


class BayesianOptimizer:
    """Bayesian Optimization optimizer using optuna TPE sampler."""

    def optimize(
        self,
        objective_fn: callable,
        search_space: SearchSpace,
        seed: int,
        termination: TerminationConfig,
    ) -> OptResult:
        """Run Bayesian optimization."""
        import optuna

        n_trials = termination.max_evaluations or 50

        # Suppress optuna output
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=seed),
        )

        tracker = ConvergenceTracker()
        best_params: dict[str, object] = {}
        best_fitness = Decimal("-Infinity")

        def objective(trial: optuna.Trial) -> float:
            nonlocal best_params, best_fitness

            params = _suggest_params(trial, search_space)
            fitness = quantize_metric(objective_fn(params))

            if fitness > best_fitness:
                best_fitness = fitness
                best_params = params

            tracker.record(trial.number + 1, best_fitness)
            return float(fitness)

        study.optimize(objective, n_trials=n_trials)

        return OptResult(
            best_params=best_params,
            best_fitness=best_fitness,
            convergence=tracker,
            n_evaluations=n_trials,
        )


def _suggest_params(trial: optuna.Trial, space: SearchSpace) -> dict:
    """Suggest parameters from the search space."""
    params = {}
    for param in space.params:
        if param.param_type == "continuous":
            params[param.name] = trial.suggest_float(param.name, param.low, param.high)  # type: ignore
        elif param.param_type == "discrete":
            params[param.name] = trial.suggest_categorical(param.name, list(param.choices))  # type: ignore
        elif param.param_type == "integer":
            params[param.name] = trial.suggest_int(param.name, int(param.low), int(param.high) - 1)  # type: ignore
    return params


__all__ = ["BayesianOptimizer"]
