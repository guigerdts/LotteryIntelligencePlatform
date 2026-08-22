"""Unit tests for dl.lstm — LotteryLSTM (DLE-02)."""

from __future__ import annotations

import pytest
import torch

from backend.app.dl.lstm import (
    DEFAULT_DROPOUT,
    DEFAULT_HIDDEN_SIZE,
    DEFAULT_NUM_LAYERS,
    N_FEATURES,
    LotteryLSTM,
)


def test_lstm_construction_defaults() -> None:
    """LSTM with default params constructs without error."""
    model = LotteryLSTM()
    assert model.hidden_size == DEFAULT_HIDDEN_SIZE
    assert model.num_layers == DEFAULT_NUM_LAYERS
    assert model.dropout == DEFAULT_DROPOUT


def test_lstm_custom_hidden_size() -> None:
    """LSTM with custom hidden size."""
    model = LotteryLSTM(hidden_size=128)
    assert model.hidden_size == 128


def test_lstm_custom_layers() -> None:
    """LSTM with custom layer count."""
    model = LotteryLSTM(num_layers=3)
    assert model.num_layers == 3


def test_lstm_custom_dropout() -> None:
    """LSTM with custom dropout."""
    model = LotteryLSTM(dropout=0.3)
    assert model.dropout == 0.3


def test_lstm_input_shape_batch() -> None:
    """LSTM accepts (batch, W, 10) input."""
    model = LotteryLSTM()
    x = torch.randn(4, 10, N_FEATURES)
    out = model(x)
    assert out.shape == (4, 10)


def test_lstm_input_shape_single() -> None:
    """LSTM accepts single sample (1, W, 10)."""
    model = LotteryLSTM()
    x = torch.randn(1, 10, N_FEATURES)
    out = model(x)
    assert out.shape == (1, 10)


def test_lstm_output_sigmoid_range() -> None:
    """LSTM output is in [0, 1] (sigmoid)."""
    model = LotteryLSTM()
    x = torch.randn(8, 10, N_FEATURES)
    out = model(x)
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_lstm_output_dtype() -> None:
    """LSTM output is float32."""
    model = LotteryLSTM()
    x = torch.randn(4, 10, N_FEATURES)
    out = model(x)
    assert out.dtype == torch.float32


def test_lstm_forward_deterministic() -> None:
    """Same input → same output (deterministic forward)."""
    model = LotteryLSTM()
    model.eval()
    x = torch.randn(4, 10, N_FEATURES)
    out1 = model(x)
    out2 = model(x)
    assert torch.equal(out1, out2)


def test_lstm_count_parameters() -> None:
    """Parameter count matches expected architecture."""
    # LSTM(input=N_FEATURES=8, hidden=64, layers=2):
    #   layer1: 4*64*8 + 4*64*64 + 2*256 = 18944; layer2: 16384+16384+512 = 33280
    # Linear(64, 10): 640+10 = 650 params → total 52874
    model = LotteryLSTM()
    assert model.count_parameters() == 52874


def test_lstm_get_hyperparameters() -> None:
    """Hyperparameters dict matches constructor args."""
    model = LotteryLSTM(hidden_size=32, num_layers=1, dropout=0.0)
    hp = model.get_hyperparameters()
    assert hp["hidden_size"] == 32
    assert hp["num_layers"] == 1
    assert hp["dropout"] == 0.0


def test_lstm_rejects_num_layers_0() -> None:
    """num_layers=0 raises ValueError."""
    with pytest.raises(ValueError, match="num_layers"):
        LotteryLSTM(num_layers=0)


def test_lstm_rejects_hidden_size_0() -> None:
    """hidden_size=0 raises ValueError."""
    with pytest.raises(ValueError, match="hidden_size"):
        LotteryLSTM(hidden_size=0)


def test_lstm_rejects_negative_dropout() -> None:
    """Negative dropout raises ValueError."""
    with pytest.raises(ValueError, match="dropout"):
        LotteryLSTM(dropout=-0.1)


def test_lstm_rejects_dropout_ge_1() -> None:
    """Dropout >= 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="dropout"):
        LotteryLSTM(dropout=1.0)


def test_lstm_single_layer_no_dropout() -> None:
    """Single-layer LSTM: dropout forced to 0 regardless of input."""
    model = LotteryLSTM(num_layers=1, dropout=0.5)
    # dropout param stored but effective_dropout=0 in nn.LSTM
    assert model.dropout == 0.5
    # Verify it still runs without error
    x = torch.randn(2, 5, N_FEATURES)
    out = model(x)
    assert out.shape == (2, 10)


def test_lstm_registered_in_registry() -> None:
    """LSTM slug exists in core-3 registry."""
    from backend.app.dl.registry import build_dl_registry

    reg = build_dl_registry()
    assert "lstm" in reg
    assert "hidden_size" in reg["lstm"]
    assert "num_layers" in reg["lstm"]
    assert "dropout" in reg["lstm"]


def test_lstm_varies_with_params() -> None:
    """Different hidden_size produces different parameter counts."""
    m1 = LotteryLSTM(hidden_size=32)
    m2 = LotteryLSTM(hidden_size=64)
    assert m2.count_parameters() > m1.count_parameters()
