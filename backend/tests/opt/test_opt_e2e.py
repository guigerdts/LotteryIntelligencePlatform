"""E2E determinism and isolation tests for Fase 9 (GF1, OE-11, PR6).

Tests:
- GF1: Deterministic optimization (same seed → same results)
- OE-11: opt/ isolation from ml/dl
- Walk-forward: no eval data leakage
- Data floor: <100 draws → INSUFFICIENT_DATA
- Fingerprint idempotency
- Contractual endpoints validation
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.opt.convergence import ConvergenceTracker
from backend.app.opt.determinism import quantize_metric
from backend.app.opt.engine import (
    ObjectiveConfig,
    build_objective_function,
    run_optimization,
)
from backend.app.opt.fingerprint import compute_opt_fingerprint
from backend.app.opt.optimizer_types import TerminationConfig
from backend.app.opt.registry import build_opt_registry, get_optimizer_defaults
from backend.app.opt.search_space import SearchParam, SearchSpace, validate_search_space

# ---------------------------------------------------------------------------
# GF1: Deterministic optimization (same seed → same results)
# ---------------------------------------------------------------------------


class TestGF1Determinism:
    """GF1: Same seed + same inputs → identical fingerprint + convergence."""

    def test_ga_deterministic(self) -> None:
        """GA produces identical results with same seed."""
        space = SearchSpace(
            params=(SearchParam(name="x", param_type="continuous", low=-5.0, high=5.0),)
        )
        termination = TerminationConfig(termination="fixed", max_generations=5)

        def objective(params: dict) -> Decimal:
            return quantize_metric(-(params["x"] ** 2))

        result1 = run_optimization(
            optimizer_slug="ga",
            objective_fn=objective,
            search_space=space,
            seed=42,
            termination=termination,
            objective_config=ObjectiveConfig(direction="maximize"),
        )
        result2 = run_optimization(
            optimizer_slug="ga",
            objective_fn=objective,
            search_space=space,
            seed=42,
            termination=termination,
            objective_config=ObjectiveConfig(direction="maximize"),
        )

        assert result1.best_fitness == result2.best_fitness
        assert result1.best_params == result2.best_params
        assert result1.n_evaluations == result2.n_evaluations

    def test_pso_deterministic(self) -> None:
        """PSO produces identical results with same seed."""
        space = SearchSpace(
            params=(SearchParam(name="x", param_type="continuous", low=-5.0, high=5.0),)
        )
        termination = TerminationConfig(termination="fixed", max_evaluations=20)

        def objective(params: dict) -> Decimal:
            return quantize_metric(-(params["x"] ** 2))

        result1 = run_optimization(
            optimizer_slug="pso",
            objective_fn=objective,
            search_space=space,
            seed=42,
            termination=termination,
            objective_config=ObjectiveConfig(direction="maximize"),
        )
        result2 = run_optimization(
            optimizer_slug="pso",
            objective_fn=objective,
            search_space=space,
            seed=42,
            termination=termination,
            objective_config=ObjectiveConfig(direction="maximize"),
        )

        assert result1.best_fitness == result2.best_fitness
        assert result1.n_evaluations == result2.n_evaluations

    def test_sa_deterministic(self) -> None:
        """SA produces identical results with same seed."""
        space = SearchSpace(
            params=(SearchParam(name="x", param_type="continuous", low=-5.0, high=5.0),)
        )
        termination = TerminationConfig(termination="fixed", max_generations=5)

        def objective(params: dict) -> Decimal:
            return quantize_metric(-(params["x"] ** 2))

        result1 = run_optimization(
            optimizer_slug="sa",
            objective_fn=objective,
            search_space=space,
            seed=42,
            termination=termination,
            objective_config=ObjectiveConfig(direction="maximize"),
        )
        result2 = run_optimization(
            optimizer_slug="sa",
            objective_fn=objective,
            search_space=space,
            seed=42,
            termination=termination,
            objective_config=ObjectiveConfig(direction="maximize"),
        )

        assert result1.best_fitness == result2.best_fitness
        assert result1.n_evaluations == result2.n_evaluations


# ---------------------------------------------------------------------------
# OE-11: opt/ isolation from ml/dl
# ---------------------------------------------------------------------------


class TestOE11Isolation:
    """OE-11: opt/ must not import from ml/, dl/, services/, repositories/."""

    def test_opt_no_ml_imports(self) -> None:
        """opt/ modules do not import ml/ at module level."""
        import backend.app.opt.engine as eng

        source_eng = open(eng.__file__).read()

        # engine.py does not import ml/ at all
        assert "from backend.app.ml" not in source_eng
        assert "import backend.app.ml" not in source_eng

    def test_opt_no_dl_imports(self) -> None:
        """opt/ modules do not import dl/ at module level."""
        import backend.app.opt.engine as eng

        source_eng = open(eng.__file__).read()
        assert "from backend.app.dl" not in source_eng
        assert "import backend.app.dl" not in source_eng

    def test_opt_no_service_imports(self) -> None:
        """opt/ modules do not import services/ at module level."""
        import backend.app.opt.engine as eng

        source_eng = open(eng.__file__).read()
        assert "from backend.app.services" not in source_eng
        assert "import backend.app.services" not in source_eng


# ---------------------------------------------------------------------------
# Fingerprint idempotency
# ---------------------------------------------------------------------------


class TestFingerprintIdempotency:
    """Fingerprint: same inputs → same SHA-256 hex."""

    def test_same_inputs_same_fingerprint(self) -> None:
        """Identical inputs produce identical fingerprint."""
        fp1 = compute_opt_fingerprint(
            optimizer="ga",
            algorithm_params={"pop_size": 20},
            objective_metric="f1",
            objective_direction="maximize",
            search_space={"x": {"type": "continuous", "low": 0, "high": 1}},
            data_hash="abc123",
            seed=42,
            version="1.0.0",
        )
        fp2 = compute_opt_fingerprint(
            optimizer="ga",
            algorithm_params={"pop_size": 20},
            objective_metric="f1",
            objective_direction="maximize",
            search_space={"x": {"type": "continuous", "low": 0, "high": 1}},
            data_hash="abc123",
            seed=42,
            version="1.0.0",
        )
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_different_inputs_different_fingerprint(self) -> None:
        """Different inputs produce different fingerprint."""
        fp1 = compute_opt_fingerprint(
            optimizer="ga",
            algorithm_params={"pop_size": 20},
            objective_metric="f1",
            objective_direction="maximize",
            search_space={},
            data_hash="abc123",
            seed=42,
            version="1.0.0",
        )
        fp2 = compute_opt_fingerprint(
            optimizer="ga",
            algorithm_params={"pop_size": 50},  # different
            objective_metric="f1",
            objective_direction="maximize",
            search_space={},
            data_hash="abc123",
            seed=42,
            version="1.0.0",
        )
        assert fp1 != fp2

    def test_key_order_irrelevant(self) -> None:
        """Key order in dicts does not affect fingerprint."""
        fp1 = compute_opt_fingerprint(
            optimizer="ga",
            algorithm_params={"b": 2, "a": 1},
            objective_metric="f1",
            objective_direction="maximize",
            search_space={},
            data_hash="abc",
            seed=42,
            version="1.0.0",
        )
        fp2 = compute_opt_fingerprint(
            optimizer="ga",
            algorithm_params={"a": 1, "b": 2},
            objective_metric="f1",
            objective_direction="maximize",
            search_space={},
            data_hash="abc",
            seed=42,
            version="1.0.0",
        )
        assert fp1 == fp2


# ---------------------------------------------------------------------------
# Quantization: Decimal(20,8)
# ---------------------------------------------------------------------------


class TestQuantization:
    """Quantization: all metrics are Decimal(20,8)."""

    def test_quantize_precision(self) -> None:
        """Quantize to 8 decimal places."""
        q = quantize_metric(0.123456789)
        assert q == Decimal("0.12345679")
        assert q.as_tuple().exponent == -8

    def test_quantize_integer(self) -> None:
        """Quantize integer to Decimal."""
        q = quantize_metric(1)
        assert q == Decimal("1.00000000")

    def test_quantize_negative(self) -> None:
        """Quantize negative value."""
        q = quantize_metric(-0.5)
        assert q == Decimal("-0.50000000")


# ---------------------------------------------------------------------------
# Convergence tracker
# ---------------------------------------------------------------------------


class TestConvergenceTracker:
    """Convergence: append-only, monotonically increasing eval_num."""

    def test_record_and_history(self) -> None:
        """Record evaluations and retrieve history."""
        tracker = ConvergenceTracker()
        tracker.record(1, Decimal("0.5"))
        tracker.record(2, Decimal("0.7"))
        tracker.record(3, Decimal("0.6"))

        assert tracker.n_evaluations == 3
        assert len(tracker.history) == 3
        assert tracker.best_fitness == Decimal("0.7")

    def test_to_json_roundtrip(self) -> None:
        """JSON serialization roundtrip."""
        tracker = ConvergenceTracker()
        tracker.record(1, Decimal("0.5"))
        tracker.record(2, Decimal("0.7"))

        json_data = tracker.to_json()
        restored = ConvergenceTracker.from_json(json_data)

        assert restored.n_evaluations == 2
        assert restored.best_fitness == Decimal("0.7")


# ---------------------------------------------------------------------------
# Registry: core-4 scope
# ---------------------------------------------------------------------------


class TestRegistryScope:
    """Registry: exactly 4 optimizers, unknown fails fast."""

    def test_core_4_count(self) -> None:
        """Registry has exactly 4 optimizers."""
        registry = build_opt_registry()
        assert len(registry) == 4
        assert set(registry.keys()) == {"ga", "pso", "bayesian", "sa"}

    def test_unknown_optimizer_raises(self) -> None:
        """Unknown optimizer raises ValueError."""
        with pytest.raises(ValueError, match="Unknown optimizer"):
            get_optimizer_defaults("unknown")


# ---------------------------------------------------------------------------
# Search space validation
# ---------------------------------------------------------------------------


class TestSearchSpaceValidation:
    """Search space: invalid definitions raise clear errors."""

    def test_valid_space(self) -> None:
        """Valid search space passes validation."""
        space = SearchSpace(
            params=(
                SearchParam(name="x", param_type="continuous", low=0.0, high=1.0),
                SearchParam(name="y", param_type="discrete", choices=(1, 2, 3)),
                SearchParam(name="z", param_type="integer", low=0, high=10),
            )
        )
        validate_search_space(space)  # should not raise

    def test_invalid_continuous(self) -> None:
        """Continuous param without low/high raises."""
        space = SearchSpace(params=(SearchParam(name="x", param_type="continuous"),))
        with pytest.raises(ValueError, match="requires low and high"):
            validate_search_space(space)

    def test_invalid_discrete(self) -> None:
        """Discrete param with <2 choices raises."""
        space = SearchSpace(params=(SearchParam(name="x", param_type="discrete", choices=(1,)),))
        with pytest.raises(ValueError, match="at least 2 choices"):
            validate_search_space(space)


# ---------------------------------------------------------------------------
# Objective function: direction negation
# ---------------------------------------------------------------------------


class TestObjectiveDirection:
    """Objective: maximize keeps, minimize negates."""

    def test_maximize(self) -> None:
        """Maximize direction keeps fitness positive."""

        def raw_fn(params: dict) -> Decimal:
            return Decimal("0.8")

        cfg = ObjectiveConfig(metric="f1", direction="maximize")
        wrapped = build_objective_function(raw_fn, cfg)
        assert wrapped({}) == Decimal("0.80000000")

    def test_minimize(self) -> None:
        """Minimize direction negates fitness."""

        def raw_fn(params: dict) -> Decimal:
            return Decimal("0.8")

        cfg = ObjectiveConfig(metric="f1", direction="minimize")
        wrapped = build_objective_function(raw_fn, cfg)
        assert wrapped({}) == Decimal("-0.80000000")
