"""LSTM model for DL lottery prediction (DLE-02 / D-A8).

Architecture: ``(W, 10) → LSTM → Linear → Sigmoid``.  Sequence-to-one using
the last hidden state of the final LSTM layer.  Deterministic under
``configure_deterministic_torch`` (seed 0, ``use_deterministic_algorithms(True)``,
1 CPU thread).

Parameters flow to the fingerprint via ``hyperparameters["lstm"]`` so any change
to architecture or defaults produces a new fingerprint (DLE-08).
"""

from __future__ import annotations

from typing import Final

import torch
import torch.nn as nn

# Canonical architecture defaults (DLE-02).
DEFAULT_HIDDEN_SIZE: Final[int] = 64
DEFAULT_NUM_LAYERS: Final[int] = 2
DEFAULT_DROPOUT: Final[float] = 0.1
N_FEATURES: Final[int] = 10
N_NUMBERS: Final[int] = 10


class LotteryLSTM(nn.Module):
    """LSTM for per-number binary classification (participation in draw n+1).

    Uses the last hidden state of the final LSTM layer, projected through a
    linear head to produce a single logit per sample, then sigmoid.

    Parameters
    ----------
    hidden_size:
        LSTM hidden dimension.  Default ``64``.
    num_layers:
        Number of stacked LSTM layers.  Default ``2``.
    dropout:
        Dropout between LSTM layers (not on the last layer).  Default ``0.1``.
    """

    def __init__(
        self,
        hidden_size: int = DEFAULT_HIDDEN_SIZE,
        num_layers: int = DEFAULT_NUM_LAYERS,
        dropout: float = DEFAULT_DROPOUT,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout

        if num_layers < 1:
            raise ValueError(f"num_layers must be >= 1, got {num_layers}")
        if hidden_size < 1:
            raise ValueError(f"hidden_size must be >= 1, got {hidden_size}")
        if dropout < 0.0 or dropout >= 1.0:
            raise ValueError(f"dropout must be in [0, 1), got {dropout}")

        # dropout is applied between layers; when num_layers=1, dropout must=0
        effective_dropout = dropout if num_layers > 1 else 0.0

        self.lstm = nn.LSTM(
            input_size=N_FEATURES,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=effective_dropout,
        )
        self.head = nn.Linear(hidden_size, N_NUMBERS)

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
        # lstm_out: (batch, W, hidden_size)
        lstm_out, _ = self.lstm(x)
        # Take the last timestep's hidden state
        last_hidden = lstm_out[:, -1, :]  # (batch, hidden_size)
        logits = self.head(last_hidden)   # (batch, 10)
        return torch.sigmoid(logits)

    def count_parameters(self) -> int:
        """Total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_hyperparameters(self) -> dict[str, object]:
        """Return architecture params for fingerprint participation."""
        return {
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
        }


__all__ = [
    "DEFAULT_DROPOUT",
    "DEFAULT_HIDDEN_SIZE",
    "DEFAULT_NUM_LAYERS",
    "N_FEATURES",
    "LotteryLSTM",
]
