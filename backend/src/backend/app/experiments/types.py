"""Experiment domain types (EXP-005/006).

Dataclasses for experiment configuration and comparison results.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExperimentConfig:
    """Configuration for an experiment run.

    Stores arbitrary engine-specific configuration as a dict.
    The ``config_json`` column in ``exp_experiments`` persists this as JSON.
    """

    params: dict[str, object] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Result of a cross-run comparison (EXP-005).

    Holds the comparison matrix keyed by run_label → {metric_name: value},
    plus the list of metric names for ordered display.
    """

    experiment_id: int
    runs: list[dict[str, object]] = field(default_factory=list)
    metric_names: list[str] = field(default_factory=list)
