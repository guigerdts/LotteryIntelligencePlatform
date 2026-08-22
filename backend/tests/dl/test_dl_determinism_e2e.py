"""GF1 E2E determinism — two seeded CPU runs must be byte-identical.

Two training runs on the same synthetic 130-draw fixture with identical
parameters must produce: identical fingerprints, identical quantized
metrics, identical weights bytes.  Verifies deterministic reproducibility
under ``configure_deterministic_torch`` with seed=0, CPU-only, float32.
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import torch

from backend.app.dl.determinism import (
    DL_SEED,
    compute_metrics_checksum,
    configure_deterministic_torch,
)
from backend.app.dl.engine import train
from backend.app.dl.providers import DrawRow, FeatureRow
from backend.app.dl.sequence_builder import build_tensors
from backend.app.dl.splitter import split_windows
from backend.app.dl.window import DEFAULT_WINDOW, build_windows

# ---------------------------------------------------------------------------
# Synthetic fixture: 130 draws, deterministic RNG.
# ---------------------------------------------------------------------------
N_DRAWS: int = 130  # extra draws needed as targets for eval windows
LOTTERY_ID: int = 1
# Train uses draws 1-85 → windows 10-85; eval uses draws 96-120 → windows 106-120.
# Gap draws 86-95 ensures no window straddles cut=90 (W=10: first eval draw=106-9=97>90).
CUT: int = 90


def _seeded_draws(n: int, seed: int = 42) -> list[DrawRow]:
    """Generate n deterministic draws with numbers in [1, 60]."""
    rng = random.Random(seed)
    draws: list[DrawRow] = []
    for i in range(1, n + 1):
        nums = tuple(sorted(rng.sample(range(1, 61), 10)))
        draws.append(DrawRow(draw_number=i, numbers=nums))
    return draws


def _seeded_features(
    draws: list[DrawRow],
    seed: int = 99,
) -> list[FeatureRow]:
    """Generate deterministic F4 feature rows for each draw."""
    rng = np.random.default_rng(seed)
    feature_ids = [
        "consecutive_count",
        "current_frequency",
        "decade_distribution",
        "draw_mean",
        "draw_range",
        "draw_sum",
        "low_high_ratio",
        "max_current_gap",
        "odd_even_ratio",
        "repeated_from_previous",
    ]
    rows: list[FeatureRow] = []
    for draw in draws:
        for fid in feature_ids:
            # Deterministic value based on draw_number + feature_id hash.
            base = float(draw.draw_number) * 0.01 + float(hash(fid) % 100) * 0.001
            val = float(rng.uniform(0.0, 1.0)) * 0.5 + base * 0.5
            rows.append(FeatureRow(feature_id=fid, draw_number=draw.draw_number, value=val))
    return rows


# ---------------------------------------------------------------------------
# Single training run — returns artifacts for comparison.
# ---------------------------------------------------------------------------


def _run_training(
    draws: list[DrawRow],
    features: list[FeatureRow],
    family: str,
    *,
    seed: int = DL_SEED,
) -> tuple[str, dict[str, object], bytes, str]:
    """Execute one full pipeline: window → split → build_tensors → train.

    Train draws: 1-85; eval draws: 96-120 (gap at 86-95 ensures no straddle).
    Windows are built separately for each range to avoid cross-gap straddle.
    Returns (fingerprint, metrics_dict, weights_blob, metrics_checksum).
    """
    configure_deterministic_torch(seed)

    # Train: draws 1-85, windows 10-85 (76 windows).
    train_draws = [d for d in draws if d.draw_number <= 85]
    train_features = [f for f in features if f.draw_number <= 85]
    train_windows = build_windows(train_draws, train_features, W=DEFAULT_WINDOW)

    # Eval: draws 96-120, windows 106-120 (15 windows). Target draw 121 exists (N_DRAWS=130).
    eval_draws = [d for d in draws if 96 <= d.draw_number <= 120]
    eval_features = [f for f in features if 96 <= f.draw_number <= 120]
    eval_windows = build_windows(eval_draws, eval_features, W=DEFAULT_WINDOW)

    # All draws needed for target lookup (targets come from the NEXT draw).
    all_draws = draws

    # Combine windows and split (cut=90: train<=90, eval>90, no straddle).
    combined = train_windows + eval_windows
    train_w, eval_w = split_windows(combined, cut=CUT)
    train_batch = build_tensors(train_w, all_draws)
    eval_batch = build_tensors(eval_w, all_draws)

    result = train(
        family,
        train_batch,
        eval_batch,
        epochs=10,
        batch_size=32,
        lr=1e-3,
        seed=seed,
        cut=CUT,
    )

    checksum = compute_metrics_checksum(result.metrics)
    return result.fingerprint, dict(result.metrics), result.weights_blob, checksum


# ---------------------------------------------------------------------------
# GF1 tests — byte-identical on same environment.
# ---------------------------------------------------------------------------


class TestGF1Determinism:
    """Two identical runs on CPU with seed=0 must produce byte-identical artifacts."""

    @pytest.fixture(autouse=True)
    def _seeded(self) -> None:
        """Force deterministic torch (seed=0, CPU, deterministic algorithms)."""
        configure_deterministic_torch(DL_SEED)

    def test_mlp_two_runs_identical(self) -> None:
        """Two MLP runs yield identical fingerprint, metrics, weights, and checksum."""
        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        fp1, m1, w1, ch1 = _run_training(draws, features, "mlp")
        fp2, m2, w2, ch2 = _run_training(draws, features, "mlp")

        assert fp1 == fp2, "MLP fingerprints must be byte-identical"
        assert m1 == m2, "MLP quantized metrics must be byte-identical"
        assert w1 == w2, "MLP weights bytes must be byte-identical"
        assert ch1 == ch2, "MLP metrics checksum must be byte-identical"

    def test_lstm_two_runs_identical(self) -> None:
        """Two LSTM runs yield identical fingerprint, metrics, weights, and checksum."""
        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        fp1, m1, w1, ch1 = _run_training(draws, features, "lstm")
        fp2, m2, w2, ch2 = _run_training(draws, features, "lstm")

        assert fp1 == fp2, "LSTM fingerprints must be byte-identical"
        assert m1 == m2, "LSTM quantized metrics must be byte-identical"
        assert w1 == w2, "LSTM weights bytes must be byte-identical"
        assert ch1 == ch2, "LSTM metrics checksum must be byte-identical"

    def test_cross_family_different_fingerprints(self) -> None:
        """MLP and LSTM must have different fingerprints (different architecture)."""
        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        fp_mlp, _, _, _ = _run_training(draws, features, "mlp")
        fp_lstm, _, _, _ = _run_training(draws, features, "lstm")

        assert fp_mlp != fp_lstm, "MLP and LSTM must differ"

    def test_different_seed_different_fingerprints(self) -> None:
        """Different seeds must produce different fingerprints."""
        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        fp1, _, _, _ = _run_training(draws, features, "mlp", seed=0)
        fp2, _, _, _ = _run_training(draws, features, "mlp", seed=1)

        assert fp1 != fp2, "Different seeds must yield different fingerprints"

    def test_metrics_quantized_decimal(self) -> None:
        """All metrics must be Decimal(20,8) quantized."""
        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        _, metrics, _, _ = _run_training(draws, features, "mlp")

        for key in ("accuracy", "precision", "recall", "f1", "roc_auc"):
            assert key in metrics, f"Missing metric: {key}"
            val = metrics[key]
            # Quantized metric has at most 8 decimal places.
            assert val.as_tuple().exponent >= -8, f"{key} not quantized to 8 decimals: {val}"

    def test_weights_checksum_valid(self) -> None:
        """Weights BLOB must validate and decode to tensors."""
        from backend.app.dl.weights import decode_weights, validate_weights

        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        _, _, weights_blob, _ = _run_training(draws, features, "mlp")

        # Must not raise
        assert validate_weights(weights_blob) is True

        # Decode returns state dict (tensors only).
        sd = decode_weights(weights_blob)
        assert len(sd) > 0
        for tensor in sd.values():
            assert tensor.dtype == torch.float32

    def test_fingerprint_format(self) -> None:
        """Fingerprint must be a 64-char hex SHA-256."""
        draws = _seeded_draws(N_DRAWS)
        features = _seeded_features(draws)

        fp, _, _, _ = _run_training(draws, features, "mlp")

        assert len(fp) == 64
        int(fp, 16)  # must not raise — valid hex


__all__ = ["TestGF1Determinism"]
