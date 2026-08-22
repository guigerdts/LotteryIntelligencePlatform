"""Unit tests for dl.engine — training engine (DLE-07)."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from backend.app.dl.engine import TrainResult, _build_model, _compute_metrics, train
from backend.app.dl.sequence_builder import SequenceBatch
from backend.app.dl.window import DL_FEATURE_ORDER


def _make_batch(N: int = 32, W: int = 10) -> SequenceBatch:
    """Create a synthetic SequenceBatch for testing."""
    X = np.random.RandomState(42).randn(N, W, len(DL_FEATURE_ORDER)).astype(np.float32)
    y = np.random.RandomState(42).randint(0, 2, size=(N, 10)).astype(np.float32)
    return SequenceBatch(X=X, y=y, draw_numbers=list(range(1, N + 1)))


def test_build_model_mlp() -> None:
    mlp = _build_model("mlp", 10, {"hidden_layers": [32], "activation": "relu"})
    assert mlp.W == 10


def test_build_model_lstm() -> None:
    lstm = _build_model("lstm", 10, {"hidden_size": 32, "num_layers": 1})
    assert lstm.hidden_size == 32


def test_build_model_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown family"):
        _build_model("transformer", 10, {})


def test_train_mlp_produces_result() -> None:
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=2, batch_size=16)
    assert isinstance(result, TrainResult)
    assert result.family == "mlp"
    assert result.W == 10
    assert result.seed == 0
    assert isinstance(result.weights_blob, bytes)
    assert len(result.fingerprint) == 64


def test_train_lstm_produces_result() -> None:
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("lstm", train_b, eval_b, epochs=2, batch_size=16)
    assert isinstance(result, TrainResult)
    assert result.family == "lstm"


def test_train_metrics_are_decimal() -> None:
    from decimal import Decimal

    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=1, batch_size=32)
    assert result.model.forward(torch.from_numpy(eval_b.X[:2]).float()).shape == (2, 10)
    for name, value in result.metrics.items():
        assert isinstance(value, Decimal), f"{name} is not Decimal"
        assert name in {"accuracy", "precision", "recall", "f1", "roc_auc"}


def test_train_deterministic() -> None:
    """Two runs with same data produce same fingerprint."""
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    r1 = train("mlp", train_b, eval_b, epochs=2, batch_size=16)
    r2 = train("mlp", train_b, eval_b, epochs=2, batch_size=16)
    assert r1.fingerprint == r2.fingerprint
    assert r1.metrics == r2.metrics


def test_train_different_data_different_fingerprint() -> None:
    """Different data → different fingerprint."""
    t1 = _make_batch(32, 10)
    e1 = _make_batch(16, 10)
    t2 = _make_batch(40, 10)
    e2 = _make_batch(20, 10)
    r1 = train("mlp", t1, e1, epochs=1, batch_size=32)
    r2 = train("mlp", t2, e2, epochs=1, batch_size=32)
    assert r1.fingerprint != r2.fingerprint


def test_train_weights_decodeable() -> None:
    from backend.app.dl.weights import decode_weights

    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=1, batch_size=32)
    sd = decode_weights(result.weights_blob, expected_fingerprint=result.fingerprint)
    assert len(sd) > 0
    for tensor in sd.values():
        assert tensor.dtype == torch.float32


def test_compute_metrics_basic() -> None:
    """Metrics computation with known inputs."""
    y_true = np.array([[1, 0], [1, 1], [0, 0]], dtype=np.float32)
    y_prob = np.array([[0.9, 0.1], [0.8, 0.7], [0.2, 0.3]], dtype=np.float32)
    metrics = _compute_metrics(y_true, y_prob)
    assert "accuracy" in metrics
    assert "f1" in metrics
    assert "roc_auc" in metrics


def test_compute_metrics_all_ones() -> None:
    """Single-class labels → ROC AUC = 0.5."""
    y_true = np.ones((10, 10), dtype=np.float32)
    y_prob = np.ones((10, 10), dtype=np.float32) * 0.8
    metrics = _compute_metrics(y_true, y_prob)
    assert metrics["roc_auc"] == 0.5
