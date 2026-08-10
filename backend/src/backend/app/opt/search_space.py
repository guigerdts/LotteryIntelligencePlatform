"""Search space definition and validation for optimization (OE-04).

Each optimizer accepts a search space as JSON-serializable parameter ranges.
The search space definition MUST be part of the fingerprint (OE-07). This
module provides validation and sampling utilities.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class SearchParam:
    """One parameter in the search space.

    ``param_type`` determines which fields are valid:
    - continuous: ``low`` and ``high`` are floats
    - discrete: ``choices`` is a non-empty tuple of values
    - integer: ``low`` and ``high`` are ints
    """

    name: str
    param_type: Literal["continuous", "discrete", "integer"]
    low: float | int | None = None
    high: float | int | None = None
    choices: tuple[object, ...] | None = None


@dataclass(frozen=True)
class SearchSpace:
    """Immutable collection of search parameters."""

    params: tuple[SearchParam, ...]


def validate_search_space(space: SearchSpace) -> None:
    """Validate a search space, raising ValueError on invalid definitions."""
    for param in space.params:
        if param.param_type == "continuous":
            if param.low is None or param.high is None:
                raise ValueError(f"Parameter {param.name!r} requires low and high")
            if param.low >= param.high:
                raise ValueError(
                    f"Parameter {param.name!r}: low ({param.low}) must be < high ({param.high})"
                )
        elif param.param_type == "discrete":
            if not param.choices or len(param.choices) < 2:
                raise ValueError(f"Parameter {param.name!r} requires at least 2 choices")
        elif param.param_type == "integer":
            if param.low is None or param.high is None:
                raise ValueError(f"Parameter {param.name!r} requires low and high")
            if int(param.low) >= int(param.high):
                raise ValueError(
                    f"Parameter {param.name!r}: low ({param.low}) must be < high ({param.high})"
                )
        else:
            raise ValueError(f"Parameter {param.name!r}: unknown type {param.param_type!r}")


def sample_point(space: SearchSpace, rng: random.Random) -> dict[str, Any]:
    """Sample one random point from the search space using the given RNG."""
    point: dict[str, Any] = {}
    for param in space.params:
        if param.param_type == "continuous":
            point[param.name] = rng.uniform(param.low, param.high)  # type: ignore[arg-type]
        elif param.param_type == "discrete":
            point[param.name] = rng.choice(param.choices)  # type: ignore[arg-type]
        elif param.param_type == "integer":
            point[param.name] = rng.randint(int(param.low), int(param.high) - 1)  # type: ignore[arg-type]
    return point


def search_space_to_json(space: SearchSpace) -> dict[str, object]:
    """Convert a SearchSpace to a JSON-serializable dict."""
    result: dict[str, object] = {}
    for param in space.params:
        entry: dict[str, object] = {"type": param.param_type}
        if param.param_type in ("continuous", "integer"):
            entry["low"] = param.low
            entry["high"] = param.high
        elif param.param_type == "discrete":
            entry["choices"] = list(param.choices)  # type: ignore[arg-type]
        result[param.name] = entry
    return result


def search_space_from_json(data: dict[str, Any]) -> SearchSpace:
    """Parse a JSON dict into a SearchSpace."""
    params = []
    for name, spec in data.items():
        param_type = spec["type"]
        low = spec.get("low")
        high = spec.get("high")
        choices = tuple(spec["choices"]) if "choices" in spec else None
        params.append(
            SearchParam(name=name, param_type=param_type, low=low, high=high, choices=choices)
        )
    return SearchSpace(params=tuple(params))


__all__ = [
    "SearchParam",
    "SearchSpace",
    "validate_search_space",
    "sample_point",
    "search_space_to_json",
    "search_space_from_json",
]
