"""Particle Swarm Optimization optimizer — custom implementation (OA-02).

PSO optimizes a swarm of particles in the hyperparameter space, tracking
personal best (pbest) and global best (gbest) across iterations.
"""

from __future__ import annotations

import random
from decimal import Decimal

from backend.app.opt.convergence import ConvergenceTracker
from backend.app.opt.determinism import quantize_metric
from backend.app.opt.optimizer_types import OptResult, TerminationConfig
from backend.app.opt.search_space import SearchSpace, sample_point


class PsoOptimizer:
    """Particle Swarm Optimization optimizer."""

    def optimize(
        self,
        objective_fn: callable,
        search_space: SearchSpace,
        seed: int,
        termination: TerminationConfig,
    ) -> OptResult:
        """Run PSO optimization."""
        rng = random.Random(seed)

        swarm_size = termination.max_evaluations or 20
        max_iterations = termination.max_evaluations or 50
        w = 0.7  # inertia
        c1 = 1.5  # cognitive
        c2 = 1.5  # social

        # Initialize particles
        particles = [_Particle(search_space, rng) for _ in range(swarm_size)]

        # Evaluate initial positions
        for p in particles:
            p.fitness = quantize_metric(objective_fn(p.position))

        # Initialize personal and global best
        for p in particles:
            p.pbest = dict(p.position)
            p.pbest_fitness = p.fitness

        gbest_idx = max(range(swarm_size), key=lambda i: particles[i].fitness)
        gbest = dict(particles[gbest_idx].position)
        gbest_fitness = particles[gbest_idx].fitness

        tracker = ConvergenceTracker()

        for iteration in range(max_iterations):
            for p in particles:
                # Update velocity
                for param in search_space.params:
                    r1, r2 = rng.random(), rng.random()
                    pbest_diff = _param_diff(p.pbest[param.name], p.position[param.name], param)
                    cognitive = c1 * r1 * pbest_diff
                    gbest_diff = _param_diff(gbest[param.name], p.position[param.name], param)
                    social = c2 * r2 * gbest_diff
                    p.velocity[param.name] = w * p.velocity[param.name] + cognitive + social

                # Update position
                for param in search_space.params:
                    new_val = p.position[param.name] + p.velocity[param.name]
                    p.position[param.name] = _clamp(new_val, param)

                # Evaluate
                p.fitness = quantize_metric(objective_fn(p.position))

                # Update personal best
                if p.fitness > p.pbest_fitness:
                    p.pbest = dict(p.position)
                    p.pbest_fitness = p.fitness

            # Update global best
            gen_best_idx = max(range(swarm_size), key=lambda i: particles[i].fitness)
            if particles[gen_best_idx].fitness > gbest_fitness:
                gbest = dict(particles[gen_best_idx].position)
                gbest_fitness = particles[gen_best_idx].fitness

            tracker.record(iteration + 1, gbest_fitness)

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
            best_params=gbest,
            best_fitness=gbest_fitness,
            convergence=tracker,
            n_evaluations=max_iterations * swarm_size,
        )


class _Particle:
    """A single particle in the swarm."""

    def __init__(self, space: SearchSpace, rng: random.Random) -> None:
        self.position = sample_point(space, rng)
        self.velocity: dict[str, float] = {}
        self.fitness = Decimal("0")
        self.pbest: dict[str, object] = {}
        self.pbest_fitness = Decimal("0")

        for param in space.params:
            if param.param_type == "continuous":
                self.velocity[param.name] = rng.uniform(-0.1, 0.1)
            elif param.param_type == "integer":
                self.velocity[param.name] = rng.uniform(-0.5, 0.5)
            else:
                self.velocity[param.name] = 0.0


def _param_diff(val1: object, val2: object, param: SearchParam) -> float:
    """Compute difference between two parameter values."""
    if param.param_type in ("continuous", "integer"):
        return float(val1) - float(val2)  # type: ignore
    return 0.0


def _clamp(val: float, param: SearchParam) -> object:
    """Clamp value to parameter bounds."""
    if param.param_type == "continuous":
        return max(param.low, min(param.high, val))  # type: ignore
    elif param.param_type == "integer":
        return max(int(param.low), min(int(param.high) - 1, round(val)))
    else:
        return val


from backend.app.opt.search_space import SearchParam  # noqa: E402

__all__ = ["PsoOptimizer"]
