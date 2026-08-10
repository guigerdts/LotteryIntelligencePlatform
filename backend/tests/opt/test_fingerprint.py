"""Tests for opt/fingerprint — canonical SHA-256 fingerprint (OE-07)."""

from __future__ import annotations

from backend.app.opt.fingerprint import compute_opt_fingerprint


def test_fingerprint_deterministic() -> None:
    """Same inputs produce identical hex fingerprint."""
    args = {
        "optimizer": "ga",
        "algorithm_params": {"population_size": 20},
        "objective_metric": "f1",
        "objective_direction": "maximize",
        "search_space": {"lr": {"type": "continuous", "low": 1e-5, "high": 0.1}},
        "data_hash": "abc123",
        "seed": 0,
        "version": "1.0.0",
        "termination_params": {"type": "fixed", "max_generations": 50},
    }
    fp1 = compute_opt_fingerprint(**args)
    fp2 = compute_opt_fingerprint(**args)
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex


def test_fingerprint_key_order_irrelevant() -> None:
    """Different key ordering produces identical fingerprint (sort_keys=True)."""
    fp1 = compute_opt_fingerprint(
        optimizer="ga",
        algorithm_params={"b": 2, "a": 1},
        objective_metric="f1",
        objective_direction="maximize",
        search_space={},
        data_hash="x",
        seed=0,
        version="1.0.0",
    )
    fp2 = compute_opt_fingerprint(
        optimizer="ga",
        algorithm_params={"a": 1, "b": 2},
        objective_metric="f1",
        objective_direction="maximize",
        search_space={},
        data_hash="x",
        seed=0,
        version="1.0.0",
    )
    assert fp1 == fp2


def test_fingerprint_changes_on_optimizer_change() -> None:
    """Different optimizer produces different fingerprint."""
    base = {
        "optimizer": "ga",
        "algorithm_params": {},
        "objective_metric": "f1",
        "objective_direction": "maximize",
        "search_space": {},
        "data_hash": "x",
        "seed": 0,
        "version": "1.0.0",
    }
    fp1 = compute_opt_fingerprint(**base)
    fp2 = compute_opt_fingerprint(**{**base, "optimizer": "pso"})
    assert fp1 != fp2


def test_fingerprint_changes_on_metric_change() -> None:
    """Different objective_metric produces different fingerprint."""
    base = {
        "optimizer": "ga",
        "algorithm_params": {},
        "objective_metric": "f1",
        "objective_direction": "maximize",
        "search_space": {},
        "data_hash": "x",
        "seed": 0,
        "version": "1.0.0",
    }
    fp1 = compute_opt_fingerprint(**base)
    fp2 = compute_opt_fingerprint(**{**base, "objective_metric": "roc_auc"})
    assert fp1 != fp2


def test_fingerprint_changes_on_seed_change() -> None:
    """Different seed produces different fingerprint."""
    base = {
        "optimizer": "ga",
        "algorithm_params": {},
        "objective_metric": "f1",
        "objective_direction": "maximize",
        "search_space": {},
        "data_hash": "x",
        "seed": 0,
        "version": "1.0.0",
    }
    fp1 = compute_opt_fingerprint(**base)
    fp2 = compute_opt_fingerprint(**{**base, "seed": 42})
    assert fp1 != fp2


def test_fingerprint_changes_on_termination_change() -> None:
    """Different termination_params produces different fingerprint."""
    base = {
        "optimizer": "ga",
        "algorithm_params": {},
        "objective_metric": "f1",
        "objective_direction": "maximize",
        "search_space": {},
        "data_hash": "x",
        "seed": 0,
        "version": "1.0.0",
        "termination_params": {"max_generations": 50},
    }
    fp1 = compute_opt_fingerprint(**base)
    fp2 = compute_opt_fingerprint(**{**base, "termination_params": {"max_generations": 100}})
    assert fp1 != fp2


def test_fingerprint_none_termination() -> None:
    """None termination_params is valid."""
    fp = compute_opt_fingerprint(
        optimizer="ga",
        algorithm_params={},
        objective_metric="f1",
        objective_direction="maximize",
        search_space={},
        data_hash="x",
        seed=0,
        version="1.0.0",
        termination_params=None,
    )
    assert len(fp) == 64
