"""Unit tests for generator weight construction (GEN-09)."""

from __future__ import annotations

from backend.app.generators.weighting import COLD_BOOST, build_weights


def test_build_weights_applies_cold_boost_only() -> None:
    probabilities = {1: 0.5, 2: 0.5}
    coverage = {1: "cold", 2: "normal"}
    weights = build_weights(probabilities, coverage)
    assert weights[1] == 0.5 * float(COLD_BOOST)
    assert weights[2] == 0.5


def test_build_weights_ignores_hot_and_normal() -> None:
    probabilities = {1: 0.3, 2: 0.7}
    coverage = {1: "normal", 2: "hot"}
    weights = build_weights(probabilities, coverage)
    assert weights == {1: 0.3, 2: 0.7}


def test_build_weights_preserves_key_set() -> None:
    probabilities = {1: 0.2, 2: 0.3, 3: 0.5}
    coverage = {1: "cold", 2: "normal", 3: "hot"}
    weights = build_weights(probabilities, coverage)
    assert set(weights) == {1, 2, 3}
    assert weights[1] == 0.2 * float(COLD_BOOST)
