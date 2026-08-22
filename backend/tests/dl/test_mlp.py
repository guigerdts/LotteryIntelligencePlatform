"""Unit tests for dl.mlp — LotteryMLP (DLE-02)."""

from __future__ import annotations

import pytest
import torch

from backend.app.dl.mlp import (
    DEFAULT_ACTIVATION,
    DEFAULT_DROPOUT,
    DEFAULT_HIDDEN_LAYERS,
    N_FEATURES,
    LotteryMLP,
)


def test_mlp_construction_defaults() -> None:
    """MLP with default params constructs without error."""
    model = LotteryMLP(W=10)
    assert model.W == 10
    assert model.hidden_layers == DEFAULT_HIDDEN_LAYERS
    assert model.activation == DEFAULT_ACTIVATION
    assert model.dropout == DEFAULT_DROPOUT


def test_mlp_custom_hidden_layers() -> None:
    """MLP with custom hidden layers."""
    model = LotteryMLP(W=5, hidden_layers=(128, 64, 32), activation="tanh")
    assert model.hidden_layers == (128, 64, 32)
    assert model.activation == "tanh"


def test_mlp_custom_dropout() -> None:
    """MLP with dropout."""
    model = LotteryMLP(W=10, dropout=0.3)
    assert model.dropout == 0.3


def test_mlp_input_shape_batch() -> None:
    """MLP accepts (batch, W, 10) input."""
    model = LotteryMLP(W=10)
    x = torch.randn(4, 10, N_FEATURES)
    out = model(x)
    assert out.shape == (4, 10)


def test_mlp_input_shape_single() -> None:
    """MLP accepts single sample (1, W, 10)."""
    model = LotteryMLP(W=10)
    x = torch.randn(1, 10, N_FEATURES)
    out = model(x)
    assert out.shape == (1, 10)


def test_mlp_output_sigmoid_range() -> None:
    """MLP output is in [0, 1] (sigmoid)."""
    model = LotteryMLP(W=10)
    x = torch.randn(8, 10, N_FEATURES)
    out = model(x)
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_mlp_output_dtype() -> None:
    """MLP output is float32."""
    model = LotteryMLP(W=10)
    x = torch.randn(4, 10, N_FEATURES)
    out = model(x)
    assert out.dtype == torch.float32


def test_mlp_forward_deterministic() -> None:
    """Same input → same output (deterministic forward)."""
    model = LotteryMLP(W=10)
    model.eval()
    x = torch.randn(4, 10, N_FEATURES)
    out1 = model(x)
    out2 = model(x)
    assert torch.equal(out1, out2)


def test_mlp_count_parameters() -> None:
    """Parameter count matches expected architecture."""
    # W=10, F=N_FEATURES=8 → input=80, layers=[64,32], output=10
    # 80*64+64 + 64*32+32 + 32*10+10 = 5184+2080+330 = 7594
    model = LotteryMLP(W=10)
    assert model.count_parameters() == 7594


def test_mlp_get_hyperparameters() -> None:
    """Hyperparameters dict matches constructor args."""
    model = LotteryMLP(W=5, hidden_layers=(32,), activation="tanh", dropout=0.2)
    hp = model.get_hyperparameters()
    assert hp["W"] == 5
    assert hp["hidden_layers"] == [32]
    assert hp["activation"] == "tanh"
    assert hp["dropout"] == 0.2


def test_mlp_rejects_unknown_activation() -> None:
    """Unknown activation raises ValueError."""
    with pytest.raises(ValueError, match="Unknown activation"):
        LotteryMLP(W=10, activation="unknown")


def test_mlp_rejects_negative_dropout() -> None:
    """Negative dropout raises ValueError."""
    with pytest.raises(ValueError, match="dropout"):
        LotteryMLP(W=10, dropout=-0.1)


def test_mlp_rejects_dropout_ge_1() -> None:
    """Dropout >= 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="dropout"):
        LotteryMLP(W=10, dropout=1.0)


def test_mlp_empty_hidden_layers() -> None:
    """MLP with empty hidden layers = linear model."""
    model = LotteryMLP(W=10, hidden_layers=())
    x = torch.randn(2, 10, N_FEATURES)
    out = model(x)
    assert out.shape == (2, 10)


def test_mlp_single_hidden() -> None:
    """MLP with single hidden layer."""
    model = LotteryMLP(W=5, hidden_layers=(128,))
    x = torch.randn(3, 5, N_FEATURES)
    out = model(x)
    assert out.shape == (3, 10)


def test_mlp_registered_in_registry() -> None:
    """MLP slug exists in core-3 registry."""
    from backend.app.dl.registry import build_dl_registry

    reg = build_dl_registry()
    assert "mlp" in reg
    assert "hidden_layers" in reg["mlp"]
    assert "activation" in reg["mlp"]
