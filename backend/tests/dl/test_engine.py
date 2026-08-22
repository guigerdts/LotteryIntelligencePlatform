"""Unit tests for dl.engine — training engine (DLE-07)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
import torch

from backend.app.dl.engine import TrainResult, _build_model, _compute_metrics, train
from backend.app.dl.fingerprint import compute_dl_fingerprint
from backend.app.dl.sequence_builder import SequenceBatch
from backend.app.dl.version import DL_GENERATOR_VERSION
from backend.app.dl.window import DL_FEATURE_ORDER

# Declared per-run walk-forward boundary (DLE-05); any fixed int keeps tests deterministic.
TEST_CUT: int = 24


def _make_batch(N: int = 32, W: int = 10) -> SequenceBatch:
    """Create a synthetic SequenceBatch for testing."""
    X = np.random.RandomState(42).randn(N, W, len(DL_FEATURE_ORDER)).astype(np.float32)
    y = np.random.RandomState(42).randint(0, 2, size=(N, 10)).astype(np.float32)
    return SequenceBatch(X=X, y=y, draw_numbers=list(range(1, N + 1)))


def test_build_model_mlp() -> None:
    """MLP factory builds a model bound to the declared window W."""
    mlp = _build_model("mlp", 10, {"hidden_layers": [32], "activation": "relu"})
    assert mlp.W == 10


def test_build_model_lstm() -> None:
    """LSTM factory builds a model with the declared hidden size."""
    lstm = _build_model("lstm", 10, {"hidden_size": 32, "num_layers": 1})
    assert lstm.hidden_size == 32


def test_build_model_unknown() -> None:
    """Unknown architecture names are rejected at build time."""
    with pytest.raises(ValueError, match="Unknown family"):
        _build_model("transformer", 10, {})


def test_train_mlp_produces_result() -> None:
    """One MLP training run yields a complete TrainResult contract."""
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=2, batch_size=16, cut=TEST_CUT)
    assert isinstance(result, TrainResult)
    assert result.family == "mlp"
    assert result.W == 10
    assert result.seed == 0
    assert isinstance(result.weights_blob, bytes)
    assert len(result.fingerprint) == 64


def test_train_lstm_produces_result() -> None:
    """One LSTM training run yields a complete TrainResult contract."""
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("lstm", train_b, eval_b, epochs=2, batch_size=16, cut=TEST_CUT)
    assert isinstance(result, TrainResult)
    assert result.family == "lstm"


def test_train_metrics_are_decimal() -> None:
    """All reported metrics are Decimal-quantized core-5 values."""
    from decimal import Decimal

    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=1, batch_size=32, cut=TEST_CUT)
    assert result.model.forward(torch.from_numpy(eval_b.X[:2]).float()).shape == (2, 10)
    for name, value in result.metrics.items():
        assert isinstance(value, Decimal), f"{name} is not Decimal"
        assert name in {"accuracy", "precision", "recall", "f1", "roc_auc"}


def test_train_deterministic() -> None:
    """Two runs with same data produce same fingerprint."""
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    r1 = train("mlp", train_b, eval_b, epochs=2, batch_size=16, cut=TEST_CUT)
    r2 = train("mlp", train_b, eval_b, epochs=2, batch_size=16, cut=TEST_CUT)
    assert r1.fingerprint == r2.fingerprint
    assert r1.metrics == r2.metrics


def test_train_different_data_different_fingerprint() -> None:
    """Different data → different fingerprint."""
    t1 = _make_batch(32, 10)
    e1 = _make_batch(16, 10)
    t2 = _make_batch(40, 10)
    e2 = _make_batch(20, 10)
    r1 = train("mlp", t1, e1, epochs=1, batch_size=32, cut=TEST_CUT)
    r2 = train("mlp", t2, e2, epochs=1, batch_size=32, cut=TEST_CUT)
    assert r1.fingerprint != r2.fingerprint


def test_train_weights_decodeable() -> None:
    """The weights blob validates against its own fingerprint and decodes to float32."""
    from backend.app.dl.weights import decode_weights

    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=1, batch_size=32, cut=TEST_CUT)
    sd = decode_weights(result.weights_blob, expected_fingerprint=result.fingerprint)
    assert len(sd) > 0
    for tensor in sd.values():
        assert tensor.dtype == torch.float32


def test_train_same_inputs_different_cut_different_fingerprint() -> None:
    """DLE-08 acceptance: changing ``cut`` changes the fingerprint."""
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    r1 = train("mlp", train_b, eval_b, epochs=1, batch_size=32, cut=10)
    r2 = train("mlp", train_b, eval_b, epochs=1, batch_size=32, cut=20)
    assert r1.fingerprint != r2.fingerprint


def test_train_different_window_different_fingerprint() -> None:
    """DLE-04/DLE-08 acceptance: changing ``W`` changes the fingerprint."""
    r1 = train(
        "mlp", _make_batch(32, 10), _make_batch(16, 10), epochs=1, batch_size=32, cut=TEST_CUT
    )
    r2 = train(
        "mlp", _make_batch(32, 12), _make_batch(16, 12), epochs=1, batch_size=32, cut=TEST_CUT
    )
    assert r1.W == 10
    assert r2.W == 12
    assert r1.fingerprint != r2.fingerprint


def test_train_threads_declared_cut_into_fingerprint() -> None:
    """Engine must digest its DECLARED ``cut``, not a hardcoded placeholder.

    Recomputing the canonical digest externally from the same inputs plus the
    declared cut reproduces the engine fingerprint byte-for-byte; the legacy
    hardcoded ``cut=0`` cannot satisfy this equality.
    """
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    result = train("mlp", train_b, eval_b, epochs=1, batch_size=32, cut=TEST_CUT)

    data_hash = hashlib.sha256(eval_b.X.tobytes() + eval_b.y.tobytes()).hexdigest()
    expected = compute_dl_fingerprint(
        data_hash=data_hash,
        hyperparameters={"mlp": result.model.get_hyperparameters()},
        architecture="mlp",
        seed=result.seed,
        window=result.W,
        cut=TEST_CUT,
        version=DL_GENERATOR_VERSION,
    )
    assert result.fingerprint == expected


def test_train_result_carries_declared_cut() -> None:
    """``TrainResult.cut`` exposes exactly the value the caller declared."""
    train_b = _make_batch(32, 10)
    eval_b = _make_batch(16, 10)
    r_mlp = train("mlp", train_b, eval_b, epochs=1, batch_size=32, cut=24)
    r_lstm = train("lstm", train_b, eval_b, epochs=1, batch_size=32, cut=13)
    assert r_mlp.cut == 24
    assert r_lstm.cut == 13


def test_train_injected_fingerprint_overrides_and_binds_weights() -> None:
    """Injected run-fingerprint wins AND the weights BLOB binds to it.

    A model-set run shares ONE run fingerprint across header + weight blobs;
    ``decode_weights`` must accept that same fingerprint as expected.
    """
    from backend.app.dl.weights import decode_weights

    run_fp = "f" * 64
    result = train(
        "mlp",
        _make_batch(32, 10),
        _make_batch(16, 10),
        epochs=1,
        batch_size=32,
        cut=TEST_CUT,
        fingerprint=run_fp,
    )
    assert result.fingerprint == run_fp
    state_dict = decode_weights(result.weights_blob, expected_fingerprint=run_fp)
    assert len(state_dict) > 0


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
