"""Tests for opt/search_space — search space validation and sampling (OE-04)."""

from __future__ import annotations

import random

import pytest

from backend.app.opt.search_space import (
    SearchParam,
    SearchSpace,
    sample_point,
    search_space_from_json,
    search_space_to_json,
    validate_search_space,
)


def test_validate_continuous_valid() -> None:
    """Valid continuous parameter passes validation."""
    param = SearchParam(name="lr", param_type="continuous", low=0.001, high=0.1)
    space = SearchSpace(params=(param,))
    validate_search_space(space)  # no raise


def test_validate_continuous_missing_bounds() -> None:
    """Continuous parameter without low/high raises ValueError."""
    space = SearchSpace(params=(SearchParam(name="lr", param_type="continuous"),))
    with pytest.raises(ValueError, match="requires low and high"):
        validate_search_space(space)


def test_validate_continuous_invalid_bounds() -> None:
    """Continuous parameter with low >= high raises ValueError."""
    param = SearchParam(name="lr", param_type="continuous", low=0.5, high=0.1)
    space = SearchSpace(params=(param,))
    with pytest.raises(ValueError, match="must be < high"):
        validate_search_space(space)


def test_validate_discrete_valid() -> None:
    """Valid discrete parameter passes validation."""
    param = SearchParam(name="batch", param_type="discrete", choices=(16, 32, 64))
    space = SearchSpace(params=(param,))
    validate_search_space(space)  # no raise


def test_validate_discrete_too_few_choices() -> None:
    """Discrete parameter with < 2 choices raises ValueError."""
    space = SearchSpace(params=(SearchParam(name="batch", param_type="discrete", choices=(16,)),))
    with pytest.raises(ValueError, match="at least 2 choices"):
        validate_search_space(space)


def test_validate_integer_valid() -> None:
    """Valid integer parameter passes validation."""
    space = SearchSpace(params=(SearchParam(name="depth", param_type="integer", low=3, high=20),))
    validate_search_space(space)  # no raise


def test_validate_unknown_type() -> None:
    """Unknown parameter type raises ValueError."""
    space = SearchSpace(params=(SearchParam(name="x", param_type="categorical"),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown type"):
        validate_search_space(space)


def test_sample_point_continuous() -> None:
    """sample_point returns float for continuous parameters."""
    param = SearchParam(name="lr", param_type="continuous", low=0.001, high=0.1)
    space = SearchSpace(params=(param,))
    rng = random.Random(42)
    point = sample_point(space, rng)
    assert isinstance(point["lr"], float)
    assert 0.001 <= point["lr"] < 0.1


def test_sample_point_discrete() -> None:
    """sample_point returns one of the choices for discrete parameters."""
    param = SearchParam(name="batch", param_type="discrete", choices=(16, 32, 64))
    space = SearchSpace(params=(param,))
    rng = random.Random(42)
    point = sample_point(space, rng)
    assert point["batch"] in (16, 32, 64)


def test_sample_point_integer() -> None:
    """sample_point returns int for integer parameters."""
    space = SearchSpace(params=(SearchParam(name="depth", param_type="integer", low=3, high=20),))
    rng = random.Random(42)
    point = sample_point(space, rng)
    assert isinstance(point["depth"], int)
    assert 3 <= point["depth"] < 20


def test_sample_point_deterministic() -> None:
    """Same seed produces same sample point."""
    param = SearchParam(name="lr", param_type="continuous", low=0.001, high=0.1)
    space = SearchSpace(params=(param,))
    p1 = sample_point(space, random.Random(42))
    p2 = sample_point(space, random.Random(42))
    assert p1 == p2


def test_search_space_roundtrip() -> None:
    """search_space_to_json -> search_space_from_json round-trips faithfully."""
    original = SearchSpace(
        params=(
            SearchParam(name="lr", param_type="continuous", low=1e-5, high=0.1),
            SearchParam(name="batch", param_type="discrete", choices=(16, 32, 64)),
            SearchParam(name="depth", param_type="integer", low=3, high=20),
        )
    )
    json_data = search_space_to_json(original)
    restored = search_space_from_json(json_data)
    assert restored == original
