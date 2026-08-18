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
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

import numpy as np

from backend.app.ml.determinism import compute_metrics_checksum, quantize_metric
from backend.app.ml.feature_reader import FeatureValueRow, build_feature_matrix
from backend.app.ml.features import ML_FEATURE_ORDER
from backend.app.ml.fingerprint import compute_ml_fingerprint
from backend.app.ml.registry import build_ml_registry
from backend.app.ml.splitter import walk_forward_split
from backend.app.ml.version import ML_GENERATOR_VERSION
from backend.app.services.errors import SnapshotNotFoundError

_METRIC_NAMES: Final[tuple[str, ...]] = ("accuracy", "precision", "recall", "f1", "roc_auc")
_POOL_MAX_WORKERS: Final[int] = 2
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
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415  # deferred: DLE-17

    if len(set(targets.tolist())) < 2:
        return quantize_metric(0.5)
    scores: np.ndarray = (
        model.decision_function(X)  # type: ignore[attr-defined]  # SVM
        if hasattr(model, "decision_function")
        else model.predict_proba(X)[:, 1]  # type: ignore[attr-defined]
    )
    return quantize_metric(float(roc_auc_score(targets, scores)))


def _fit_number(
    X_train: np.ndarray,
    X_eval: np.ndarray,
    y_train: np.ndarray,
    y_eval: np.ndarray,
    estimator_name: str,
    params: Mapping[str, object],
    number: int,
) -> tuple[int, dict[str, Decimal], object]:
    """Fit one target number's classifier and return quantized metrics (T-S4-01).

    Pure worker: no DB session/engine, no shared mutable state.  The
    estimator class is resolved from the canonical registry by name and
    instantiated with ``random_state=0`` and no shuffle, so every number
    is an independent deterministic function of its inputs — the same
    code path the serial loop uses, which keeps serial and parallel
    outputs byte-identical (GF-1).

    Returns:
        ``(number, {metric: Decimal}, model)``.
    """
    from sklearn.metrics import (  # noqa: PLC0415  # deferred: DLE-17
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )

    from backend.app.ml.registry import build_ml_registry  # noqa: PLC0415

    classifier, _ = build_ml_registry()[estimator_name]
    model = classifier(**dict(params)).fit(X_train, y_train)
    predict = model.predict(X_eval)
    metrics = {
        "accuracy": quantize_metric(accuracy_score(y_eval, predict)),
        "precision": quantize_metric(precision_score(y_eval, predict, zero_division=1)),
        "recall": quantize_metric(recall_score(y_eval, predict, zero_division=1)),
        "f1": quantize_metric(f1_score(y_eval, predict, zero_division=1)),
        "roc_auc": _roc_auc(y_eval, model, X_eval),
    }
    return number, metrics, model


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
        parallel: bool = False,
    ) -> TrainResult:
        """Run one deterministic training for ``family`` over ``lottery_id``.

        An absent ``feature_rows`` raises ``SNAPSHOT_NOT_FOUND`` BEFORE any
        training (MLE-06).  ``parallel`` uses a bounded ``ProcessPoolExecutor``
        over the sorted number list; the serial loop and the pool share the
        same ``_fit_number`` worker so results are byte-identical (GF-1).
        """
        entry = self.registry.get(family)
        if entry is None:
            raise ValueError(f"unknown family {family!r}; known: {sorted(self.registry)}")
        _, params = entry

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
        if parallel and len(all_numbers) >= 2:
            with ProcessPoolExecutor(max_workers=_POOL_MAX_WORKERS) as executor:
                fitted = executor.map(
                    _fit_number,
                    [X_train] * len(all_numbers),
                    [X_eval] * len(all_numbers),
                    [y[n][train_idx] for n in all_numbers],
                    [y[n][eval_idx] for n in all_numbers],
                    [family] * len(all_numbers),
                    [dict(params)] * len(all_numbers),
                    all_numbers,
                )
                for number, metrics, model in fitted:
                    per_number[number] = metrics
                    models[number] = model
        else:
            for number in all_numbers:
                fitted = _fit_number(
                    X_train,
                    X_eval,
                    y[number][train_idx],
                    y[number][eval_idx],
                    family,
                    dict(params),
                    number,
                )
                per_number[fitted[0]] = fitted[1]
                models[fitted[0]] = fitted[2]

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
