"""Pure ML training engine (ME-01..05, MLE-03/04/05, design "engine.py").

``MlEngine.train`` fits one core-5 family per lottery: ``X`` = per-draw F4 vector in
fixed ``ML_FEATURE_ORDER`` (rows via ``FeatureSnapshotReader``, MLE-06), ``y`` =
per-number participation in draw ``n+1`` (D3), walk-forward split (``train <= cut <
eval``). Metrics quantize to Decimal ``Numeric(20,8)`` before any checksum (MLE-05).
Pure: draws + rows in, ``TrainResult`` out — no DB, no ``probability_service``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from backend.app.ml.determinism import compute_metrics_checksum, quantize_metric
from backend.app.ml.feature_reader import FeatureValueRow, build_feature_matrix
from backend.app.ml.features import ML_FEATURE_ORDER
from backend.app.ml.fingerprint import compute_ml_fingerprint
from backend.app.ml.registry import build_ml_registry
from backend.app.ml.splitter import walk_forward_split
from backend.app.ml.version import ML_GENERATOR_VERSION
from backend.app.services.errors import SnapshotNotFoundError

_METRIC_NAMES: Final[tuple[str, ...]] = ("accuracy", "precision", "recall", "f1", "roc_auc")
_Draw = Mapping | object  # duck-typed record: mapping key or attribute


@dataclass(frozen=True, slots=True)
class TrainResult:
    """Deterministic outcome of one family-lottery training run."""

    family: str
    lottery_id: int
    snapshot_id: int
    cut: int
    features: tuple[str, ...]
    metrics: Mapping[str, Decimal]  # aggregated over target numbers
    quantized: Mapping[int, Mapping[str, Decimal]]  # per-number Decimal(20,8) metrics
    models: Mapping[int, object]  # one fitted classifier per number
    fingerprint: str
    checksum: str
    train_draws: tuple[int, ...]
    eval_draws: tuple[int, ...]


def _get(record: _Draw, key: str) -> object:
    """Read ``key`` from a record, mapping or attribute-bearing (duck-typed)."""
    return record[key] if isinstance(record, Mapping) else getattr(record, key)  # type: ignore[attr-defined]


def _roc_auc(targets: np.ndarray, model: object, X: np.ndarray) -> Decimal:
    """AUC from decision scores; chance baseline when the eval split has one class."""
    if len(set(targets.tolist())) < 2:
        return quantize_metric(0.5)
    scores: np.ndarray = (
        model.decision_function(X)  # type: ignore[attr-defined]  # SVM
        if hasattr(model, "decision_function")
        else model.predict_proba(X)[:, 1]  # type: ignore[attr-defined]
    )
    return quantize_metric(float(roc_auc_score(targets, scores)))


class MlEngine:
    """Trains one core-5 family per lottery against its F4 features (ME-01..05)."""

    def __init__(
        self, *, registry: Mapping[str, tuple[type, dict[str, object]]] | None = None
    ) -> None:
        self.registry = build_ml_registry() if registry is None else registry

    def train(
        self,
        family: str,
        lottery_id: int,
        records: Sequence[object],
        snapshot_id: int,
        metadata: Mapping[str, object] | None = None,
        *,
        cut: int | None = None,
        feature_rows: Sequence[FeatureValueRow] | None = None,
    ) -> TrainResult:
        """Run one deterministic training for ``family`` over ``lottery_id``.

        An absent ``feature_rows`` raises ``SNAPSHOT_NOT_FOUND`` BEFORE any
        training (MLE-06).
        """
        entry = self.registry.get(family)
        if entry is None:
            raise ValueError(f"unknown family {family!r}; known: {sorted(self.registry)}")
        classifier, params = entry

        if feature_rows is None:
            raise SnapshotNotFoundError(f"no F4 feature snapshot for snapshot_id={snapshot_id}")
        X, matrix_draws = build_feature_matrix(feature_rows)

        draws = sorted(records, key=lambda r: int(_get(r, "draw_number")))  # never shuffles (D2)
        frame = draws[:-1]  # rows at ``n`` carry targets from draw ``n+1`` (D3)
        row_draws = [int(_get(r, "draw_number")) for r in frame]
        index_of = {draw: i for i, draw in enumerate(matrix_draws)}
        X = X[[index_of[draw] for draw in row_draws]]

        if cut is None:
            cut = len(frame) * 4 // 5  # M-A8 default
        train_seg, eval_seg = walk_forward_split(frame, cut)  # fails fast on a bad cut
        train_idx = [index_of[int(_get(r, "draw_number"))] for r in train_seg]
        eval_idx = [index_of[int(_get(r, "draw_number"))] for r in eval_seg]
        X_train, X_eval = X[train_idx], X[eval_idx]

        all_numbers = sorted({n for r in records for n in _get(r, "numbers")})
        y = {n: np.zeros(len(frame), dtype=int) for n in all_numbers}
        for i in range(len(frame)):
            for n in _get(draws[i + 1], "numbers"):
                y[n][i] = 1

        models: dict[int, object] = {}
        per_number: dict[int, dict[str, Decimal]] = {}
        for number in all_numbers:
            model = classifier(**dict(params)).fit(X_train, y[number][train_idx])
            predict = model.predict(X_eval)
            targets = y[number][eval_idx]
            per_number[number] = {
                "accuracy": quantize_metric(accuracy_score(targets, predict)),
                "precision": quantize_metric(precision_score(targets, predict, zero_division=1)),
                "recall": quantize_metric(recall_score(targets, predict, zero_division=1)),
                "f1": quantize_metric(f1_score(targets, predict, zero_division=1)),
                "roc_auc": _roc_auc(targets, model, X_eval),
            }
            models[number] = model

        metrics = {
            name: quantize_metric(sum(per_number[n][name] for n in all_numbers) / len(all_numbers))
            for name in _METRIC_NAMES
        }
        data_hash = hashlib.sha256(
            json.dumps(
                {
                    "lottery_id": lottery_id,
                    "snapshot_id": snapshot_id,
                    "draws": [
                        [int(_get(r, "draw_number")), sorted(_get(r, "numbers"))] for r in draws
                    ],
                    "metadata": dict(metadata) if metadata else {},
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return TrainResult(
            family=family,
            lottery_id=lottery_id,
            snapshot_id=snapshot_id,
            cut=cut,
            features=tuple(ML_FEATURE_ORDER),
            metrics=metrics,
            quantized=per_number,
            models=models,
            fingerprint=compute_ml_fingerprint(data_hash, params, ML_GENERATOR_VERSION, cut),
            checksum=compute_metrics_checksum(metrics),
            train_draws=tuple(row_draws[i] for i in train_idx),
            eval_draws=tuple(row_draws[i] for i in eval_idx),
        )


__all__ = ["MlEngine", "TrainResult"]
