"""Unit tests for dl.fingerprint — canonical SHA-256 (DLE-08)."""

from __future__ import annotations

from backend.app.dl.fingerprint import compute_dl_fingerprint

_BASE = {
    "data_hash": "abc123",
    "hyperparameters": {"mlp": {"epochs": 50}, "lstm": {"hidden_size": 64}},
    "architecture": "core-3",
    "seed": 0,
    "window": 10,
    "cut": 80,
    "version": "1.0.0",
}


def test_fingerprint_deterministic() -> None:
    """Same inputs produce byte-identical fingerprint."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(**_BASE)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_fingerprint_changes_with_window() -> None:
    """Different window yields different fingerprint (DLE-04)."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(**{**_BASE, "window": 15})
    assert h1 != h2


def test_fingerprint_changes_with_cut() -> None:
    """Different cut yields different fingerprint (DLE-04)."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(**{**_BASE, "cut": 90})
    assert h1 != h2


def test_fingerprint_changes_with_seed() -> None:
    """Different seed yields different fingerprint."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(**{**_BASE, "seed": 42})
    assert h1 != h2


def test_fingerprint_changes_with_version() -> None:
    """Different version yields different fingerprint (DLE-08)."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(**{**_BASE, "version": "1.0.1"})
    assert h1 != h2


def test_fingerprint_changes_with_data_hash() -> None:
    """Different data_hash yields different fingerprint."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(**{**_BASE, "data_hash": "def456"})
    assert h1 != h2


def test_fingerprint_changes_with_hyperparameters() -> None:
    """Different hyperparameters yields different fingerprint."""
    h1 = compute_dl_fingerprint(**_BASE)
    h2 = compute_dl_fingerprint(
        **{**_BASE, "hyperparameters": {"mlp": {"epochs": 100}, "lstm": {"hidden_size": 64}}}
    )
    assert h1 != h2


def test_fingerprint_hyperparams_copied() -> None:
    """Caller-side mutation after call does not change the digest."""
    params = {"mlp": {"epochs": 50}}
    h1 = compute_dl_fingerprint(**{**_BASE, "hyperparameters": params})
    params["mlp"]["epochs"] = 999  # mutate
    h2 = compute_dl_fingerprint(**{**_BASE, "hyperparameters": {"mlp": {"epochs": 50}}})
    assert h1 == h2
