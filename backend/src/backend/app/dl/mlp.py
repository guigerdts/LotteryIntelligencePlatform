"""MLP model for DL lottery prediction (DLE-02 / D-A8).

Architecture: ``W*10 → hidden_layers → 1`` with ReLU activations between hidden
layers and Sigmoid on the output.  Deterministic under ``configure_deterministic_torch``
(seed 0, ``use_deterministic_algorithms(True)``, 1 CPU thread).

Parameters flow to the fingerprint via ``hyperparameters["mlp"]`` so any change
to architecture or defaults produces a new fingerprint (DLE-08).
"""

from __future__ import annotations

from typing import Final

import torch
import torch.nn as nn

# Canonical architecture defaults (DLE-02).
DEFAULT_HIDDEN_LAYERS: Final[tuple[int, ...]] = (64, 32)
DEFAULT_ACTIVATION: Final[str] = "relu"
DEFAULT_DROPOUT: Final[float] = 0.0
N_FEATURES: Final[int] = 10
N_NUMBERS: Final[int] = 10

_ACTIVATION_MAP: dict[str, type[nn.Module]] = {
    "relu": nn.ReLU,
    "tanh": nn.Tanh,
    "sigmoid": nn.Sigmoid,
}


class LotteryMLP(nn.Module):
    """MLP for per-number binary classification (participation in draw n+1).

    Parameters
    ----------
    W:
        Sequence length (window size).
    hidden_layers:
        Sizes of hidden layers, applied in order.  Default ``(64, 32)``.
    activation:
        Activation between hidden layers.  Default ``"relu"``.
    dropout:
        Dropout rate applied after each hidden layer.  Default ``0.0``.
    """

    def __init__(
        self,
        W: int,
        hidden_layers: tuple[int, ...] = DEFAULT_HIDDEN_LAYERS,
        activation: str = DEFAULT_ACTIVATION,
        dropout: float = DEFAULT_DROPOUT,
    ) -> None:
        super().__init__()
        self.W = W
        self.hidden_layers = tuple(hidden_layers)
        self.activation = activation
        self.dropout = dropout

        if activation not in _ACTIVATION_MAP:
            raise ValueError(
                f"Unknown activation '{activation}'; choose from {sorted(_ACTIVATION_MAP)}"
            )
        if dropout < 0.0 or dropout >= 1.0:
            raise ValueError(f"dropout must be in [0, 1), got {dropout}")

        input_size = W * N_FEATURES
        act_cls = _ACTIVATION_MAP[activation]

        layers: list[nn.Module] = []
        prev_size = input_size
        for h in hidden_layers:
            layers.append(nn.Linear(prev_size, h))
            layers.append(act_cls())
            if dropout > 0.0:
                layers.append(nn.Dropout(dropout))
            prev_size = h

        layers.append(nn.Linear(prev_size, N_NUMBERS))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Parameters
        ----------
        x:
            Input tensor of shape ``(batch, W, 10)``.

        Returns
        -------
        torch.Tensor
            Sigmoid probabilities of shape ``(batch, 10)`` — one per number.
        """
        batch_size = x.shape[0]
        flat = x.view(batch_size, -1)  # (batch, W*10)
        logits = self.network(flat)     # (batch, 10)
        return torch.sigmoid(logits)

    def count_parameters(self) -> int:
        """Total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_hyperparameters(self) -> dict[str, object]:
        """Return architecture params for fingerprint participation."""
        return {
            "hidden_layers": list(self.hidden_layers),
            "activation": self.activation,
            "dropout": self.dropout,
            "W": self.W,
        }


__all__ = [
    "DEFAULT_ACTIVATION",
    "DEFAULT_DROPOUT",
    "DEFAULT_HIDDEN_LAYERS",
    "N_FEATURES",
    "LotteryMLP",
]
