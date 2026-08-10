"""Simulated Annealing optimizer — custom implementation (OA-04).

SA starts from a random point and cools down, accepting worse solutions
with decreasing probability to escape local optima.
"""

from __future__ import annotations

import math
import random

from backend.app.opt.convergence import ConvergenceTracker
from backend.app.opt.determinism import quantize_metric
from backend.app.opt.optimizer_types import OptResult, TerminationConfig
from backend.app.opt.search_space import SearchSpace, sample_point


class SaOptimizer:
    """Simulated Annealing optimizer."""

    def optimize(
        self,
        objective_fn: callable,
        search_space: SearchSpace,
        seed: int,
        termination: TerminationConfig,
    ) -> OptResult:
        """Run SA optimization."""
        rng = random.Random(seed)

        max_iterations = termination.max_generations or 50
        initial_temp = 1.0
        cooling_rate = 0.95
        perturbation_scale = 0.1

        # Start from random point
        current = sample_point(search_space, rng)
        current_fitness = quantize_metric(objective_fn(current))

        best = dict(current)
        best_fitness = current_fitness

        temp = initial_temp
        tracker = ConvergenceTracker()

        for iteration in range(max_iterations):
            # Generate neighbor
            neighbor = _perturb(current, search_space, rng, perturbation_scale)
            neighbor_fitness = quantize_metric(objective_fn(neighbor))

            # Accept or reject
            delta = float(neighbor_fitness - current_fitness)
            if delta > 0:
                current = neighbor
                current_fitness = neighbor_fitness
            elif temp > 0:
                probability = math.exp(delta / temp)
                if rng.random() < probability:
                    current = neighbor
                    current_fitness = neighbor_fitness

            # Update best
            if current_fitness > best_fitness:
                best = dict(current)
                best_fitness = current_fitness

            tracker.record(iteration + 1, best_fitness)

            # Cool down
            temp *= cooling_rate

            # Early stopping check
            if termination.termination == "early_stopping" and termination.patience:
                if iteration > termination.patience:
                    recent = tracker.history[-termination.patience :]
                    improvements = [
                        recent[i].best_fitness > recent[i - 1].best_fitness
                        for i in range(1, len(recent))
                    ]
                    if not any(improvements):
                        break

        return OptResult(
            best_params=best,
            best_fitness=best_fitness,
            convergence=tracker,
            n_evaluations=max_iterations,
        )


def _perturb(params: dict, space: SearchSpace, rng: random.Random, scale: float) -> dict:
    """Generate a neighbor by perturbing current parameters."""
    neighbor = dict(params)
    for param in space.params:
        if param.param_type == "continuous":
            val = neighbor[param.name]
            noise = rng.gauss(0, (param.high - param.low) * scale)  # type: ignore
            neighbor[param.name] = max(param.low, min(param.high, val + noise))  # type: ignore
        elif param.param_type == "discrete":
            neighbor[param.name] = rng.choice(param.choices)  # type: ignore
        elif param.param_type == "integer":
            val = neighbor[param.name]
            delta = rng.choice([-1, 0, 1])
            neighbor[param.name] = max(int(param.low), min(int(param.high) - 1, val + delta))  # type: ignore
    return neighbor


__all__ = ["SaOptimizer"]
