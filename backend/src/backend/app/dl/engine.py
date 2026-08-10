"""Training engine for DL models (DLE-07 / D-A8).

Trains MLP or LSTM on walk-forward splits produced by the splitter.
Adam + BCELoss, configurable epochs/batch_size, deterministic under
``configure_deterministic_torch``.  No temporal shuffle.

Returns in-memory artifacts: trained model, quantized metrics, encoded
weights BLOB, and fingerprint.  Persistence is service-layer responsibility.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Protocol

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from backend.app.dl.determinism import (
    DL_SEED,
    configure_deterministic_torch,
    quantize_metric,
)
from backend.app.dl.fingerprint import compute_dl_fingerprint
from backend.app.dl.lstm import LotteryLSTM
from backend.app.dl.mlp import LotteryMLP
from backend.app.dl.sequence_builder import SequenceBatch
from backend.app.dl.version import DL_GENERATOR_VERSION
from backend.app.dl.weights import encode_weights

N_NUMBERS: Final[int] = 10
DEFAULT_EPOCHS: Final[int] = 50
DEFAULT_BATCH_SIZE: Final[int] = 32
DEFAULT_LR: Final[float] = 1e-3


class _Model(Protocol):
    """Minimal protocol for trained DL models."""

    def forward(self, x: torch.Tensor) -> torch.Tensor: ...
    def get_hyperparameters(self) -> dict[str, object]: ...
    def state_dict(self) -> dict[str, torch.Tensor]: ...


@dataclass(frozen=True)
class TrainResult:
    """Artifacts produced by a single training run."""

    model: _Model
    family: str
    metrics: dict[str, Decimal]
    weights_blob: bytes
    fingerprint: str
    W: int
    seed: int


def _build_model(
    family: str,
    W: int,
    hyperparams: dict[str, object],
) -> _Model:
    """Instantiate a model from family name + hyperparameters."""
    if family == "mlp":
        return LotteryMLP(
            W=W,
            hidden_layers=tuple(hyperparams.get("hidden_layers", [64, 32])),
            activation=str(hyperparams.get("activation", "relu")),
            dropout=float(hyperparams.get("dropout", 0.0)),
        )
    if family == "lstm":
        return LotteryLSTM(
            hidden_size=int(hyperparams.get("hidden_size", 64)),
            num_layers=int(hyperparams.get("num_layers", 2)),
            dropout=float(hyperparams.get("dropout", 0.1)),
        )
    raise ValueError(f"Unknown family '{family}'; choose 'mlp' or 'lstm'")


def _compute_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> dict[str, Decimal]:
    """Compute per-number metrics averaged across all numbers.

    Metrics: accuracy, precision, recall, f1, roc_auc.
    Undefined precision/recall (zero division) default to 0.0.
    Undefined ROC AUC (single-class) defaults to 0.5.
    """
    y_pred = (y_prob >= 0.5).astype(np.float32)

    n_cols = y_true.shape[1]

    metrics_acc: dict[str, list[float]] = {
        "accuracy": [],
        "precision": [],
        "recall": [],
        "f1": [],
        "roc_auc": [],
    }

    for j in range(n_cols):
        tp = float(np.sum((y_true[:, j] == 1) & (y_pred[:, j] == 1)))
        fp = float(np.sum((y_true[:, j] == 0) & (y_pred[:, j] == 1)))
        fn = float(np.sum((y_true[:, j] == 1) & (y_pred[:, j] == 0)))
        tn = float(np.sum((y_true[:, j] == 0) & (y_pred[:, j] == 0)))
        total = tp + fp + fn + tn

        # Accuracy
        metrics_acc["accuracy"].append((tp + tn) / total if total > 0 else 0.0)

        # Precision
        denom_p = tp + fp
        metrics_acc["precision"].append(tp / denom_p if denom_p > 0 else 0.0)

        # Recall
        denom_r = tp + fn
        metrics_acc["recall"].append(tp / denom_r if denom_r > 0 else 0.0)

        # F1
        p = metrics_acc["precision"][-1]
        r = metrics_acc["recall"][-1]
        metrics_acc["f1"].append(2 * p * r / (p + r) if (p + r) > 0 else 0.0)

        # ROC AUC (simple trapezoidal)
        pos = y_true[:, j]
        prob = y_prob[:, j]
        n_pos = float(np.sum(pos == 1))
        n_neg = float(np.sum(pos == 0))
        if n_pos == 0 or n_neg == 0:
            metrics_acc["roc_auc"].append(0.5)
        else:
            # Sort by descending probability.
            order = np.argsort(-prob)
            pos_sorted = pos[order]
            tpr = np.cumsum(pos_sorted == 1) / n_pos
            fpr = np.cumsum(pos_sorted == 0) / n_neg
            # Prepend (0,0).
            tpr = np.concatenate([[0.0], tpr])
            fpr = np.concatenate([[0.0], fpr])
            auc = float(np.trapezoid(tpr, fpr))
            metrics_acc["roc_auc"].append(abs(auc))

    return {k: quantize_metric(np.mean(v)) for k, v in metrics_acc.items()}


def train(
    family: str,
    train_batch: SequenceBatch,
    eval_batch: SequenceBatch,
    *,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    lr: float = DEFAULT_LR,
    seed: int = DL_SEED,
) -> TrainResult:
    """Train a DL model and return in-memory artifacts.

    Parameters
    ----------
    family:
        ``"mlp"`` or ``"lstm"``.
    train_batch:
        Training data from the splitter + sequence builder.
    eval_batch:
        Evaluation data for metric computation.
    epochs:
        Training epochs.  Default 50.
    batch_size:
        Mini-batch size.  Default 32.
    lr:
        Adam learning rate.  Default 1e-3.
    seed:
        RNG seed.  Default ``DL_SEED`` (0).

    Returns
    -------
    TrainResult
        Trained model, quantized metrics, weights BLOB, fingerprint.
    """
    configure_deterministic_torch(seed)

    W = train_batch.X.shape[1]
    model = _build_model(family, W, {})

    # Convert to torch tensors (no shuffle — chronological order preserved).
    X_train = torch.from_numpy(train_batch.X).float()
    y_train = torch.from_numpy(train_batch.y).float()
    X_eval = torch.from_numpy(eval_batch.X).float()
    y_eval_np = eval_batch.y  # keep numpy for metrics

    dataset = TensorDataset(X_train, y_train)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCELoss()

    model.train()
    for _epoch in range(epochs):
        for X_batch, y_batch in loader:
            optimizer.zero_grad()
            output = model(X_batch)
            loss = criterion(output, y_batch)
            loss.backward()
            optimizer.step()

    # Eval metrics.
    model.eval()
    with torch.no_grad():
        y_prob = model(X_eval).numpy()

    metrics = _compute_metrics(y_eval_np, y_prob)

    # Fingerprint.
    # Compute data hash from the eval batch for reproducibility.
    data_hash = hashlib.sha256(eval_batch.X.tobytes() + eval_batch.y.tobytes()).hexdigest()

    hp = model.get_hyperparameters()
    fingerprint = compute_dl_fingerprint(
        data_hash=data_hash,
        hyperparameters={family: hp},
        architecture=family,
        seed=seed,
        window=W,
        cut=0,  # cut not relevant for fingerprint at engine level
        version=DL_GENERATOR_VERSION,
    )

    # Encode weights.
    weights_blob = encode_weights(
        model.state_dict(),
        fingerprint=fingerprint,
        architecture=family,
        hyperparameters=hp,
        seed=seed,
        version=DL_GENERATOR_VERSION,
        W=W,
    )

    return TrainResult(
        model=model,
        family=family,
        metrics=metrics,
        weights_blob=weights_blob,
        fingerprint=fingerprint,
        W=W,
        seed=seed,
    )


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_EPOCHS",
    "DEFAULT_LR",
    "N_NUMBERS",
    "TrainResult",
    "train",
]
