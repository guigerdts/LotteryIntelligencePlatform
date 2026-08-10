"""Optimization Engine — deterministic hyperparameter search for ML/DL models.

This package implements the ``opt-engine`` specification (OE-01..15): four
optimizers (GA, PSO, Bayesian, SA) searching configurable parameter spaces,
evaluating fitness via walk-forward validation on existing ML/DL training
pipelines. The engine is pure and DB-free; ``OptService`` is the composition
root owning one atomic transaction per run.
"""
