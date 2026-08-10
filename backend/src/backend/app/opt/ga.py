"""Genetic Algorithm optimizer using deap (OA-01).

GA evolves a population of hyperparameter vectors, evaluating fitness via
walk-forward on ML/DL training. Tournament selection, uniform crossover,
gaussian mutation, elitism.
"""

from __future__ import annotations

import random
from decimal import Decimal

from backend.app.opt.convergence import ConvergenceTracker
from backend.app.opt.determinism import quantize_metric
from backend.app.opt.optimizer_types import OptResult, TerminationConfig
from backend.app.opt.search_space import SearchSpace, sample_point


class GaOptimizer:
    """Genetic Algorithm optimizer using deap."""

    def optimize(
        self,
        objective_fn: callable,
        search_space: SearchSpace,
        seed: int,
        termination: TerminationConfig,
    ) -> OptResult:
        """Run GA optimization."""
        import random as _random

        _random.seed(seed)
        rng = random.Random(seed)

        population_size = termination.max_generations or 20
        generations = termination.max_generations or 50
        crossover_prob = 0.7
        mutation_prob = 0.2
        tournament_size = 3

        # Initialize population
        population = [sample_point(search_space, rng) for _ in range(population_size)]
        fitnesses = [_evaluate(ind, objective_fn) for ind in population]
        tracker = ConvergenceTracker()

        best_params = population[0]
        best_fitness = fitnesses[0]

        for gen in range(generations):
            # Evaluate fitness
            for i, ind in enumerate(population):
                fit = _evaluate(ind, objective_fn)
                fitnesses[i] = fit

            # Track best
            gen_best_idx = max(range(len(fitnesses)), key=lambda i: fitnesses[i])
            if fitnesses[gen_best_idx] > best_fitness:
                best_fitness = fitnesses[gen_best_idx]
                best_params = dict(population[gen_best_idx])

            tracker.record(gen + 1, best_fitness)

            # Early stopping check
            if termination.termination == "early_stopping" and termination.patience:
                if gen > termination.patience:
                    recent = tracker.history[-termination.patience :]
                    improvements = [
                        recent[i].best_fitness > recent[i - 1].best_fitness
                        for i in range(1, len(recent))
                    ]
                    if not any(improvements):
                        break

            # Selection (tournament)
            selected = []
            for _ in range(population_size):
                tournament = rng.sample(range(population_size), tournament_size)
                winner = max(tournament, key=lambda i: fitnesses[i])
                selected.append(dict(population[winner]))

            # Crossover (uniform)
            offspring = []
            for i in range(0, population_size - 1, 2):
                p1, p2 = selected[i], selected[i + 1]
                c1, c2 = _crossover(p1, p2, search_space, rng, crossover_prob)
                offspring.extend([c1, c2])
            if len(offspring) < population_size:
                offspring.append(dict(selected[-1]))

            # Mutation
            for ind in offspring:
                _mutate(ind, search_space, rng, mutation_prob)

            # Elitism: keep best individual
            population = offspring[:population_size]
            population[0] = dict(best_params)

        return OptResult(
            best_params=best_params,
            best_fitness=best_fitness,
            convergence=tracker,
            n_evaluations=generations * population_size,
        )


def _evaluate(params: dict, objective_fn: callable) -> Decimal:
    """Evaluate objective function and return quantized fitness."""
    return quantize_metric(objective_fn(params))


def _crossover(
    p1: dict, p2: dict, space: SearchSpace, rng: random.Random, prob: float
) -> tuple[dict, dict]:
    """Uniform crossover per parameter."""
    c1, c2 = dict(p1), dict(p2)
    for param in space.params:
        if rng.random() < prob:
            c1[param.name], c2[param.name] = c2[param.name], c1[param.name]
    return c1, c2


def _mutate(params: dict, space: SearchSpace, rng: random.Random, prob: float) -> None:
    """Gaussian/categorical mutation per parameter."""
    for param in space.params:
        if rng.random() < prob:
            if param.param_type == "continuous":
                val = params[param.name]
                noise = rng.gauss(0, (param.high - param.low) * 0.1)  # type: ignore
                params[param.name] = max(param.low, min(param.high, val + noise))  # type: ignore
            elif param.param_type == "discrete":
                params[param.name] = rng.choice(param.choices)  # type: ignore
            elif param.param_type == "integer":
                val = params[param.name]
                delta = rng.choice([-1, 0, 1])
                params[param.name] = max(int(param.low), min(int(param.high) - 1, val + delta))  # type: ignore


__all__ = ["GaOptimizer"]
