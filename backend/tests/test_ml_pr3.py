"""PR3 gates: engine, walk-forward split, F4 reader (T-11..T-14, MLE-03..07)."""

from __future__ import annotations

import random
from decimal import Decimal
from types import SimpleNamespace
from typing import Final

import pytest

from backend.app.ml.features import ML_FEATURE_ORDER
from backend.app.ml.registry import FUTURE_ML_FAMILIES

_NUMBERS: Final[tuple[int, ...]] = (4, 5, 6)
_METRIC_NAMES: Final[tuple[str, ...]] = ("accuracy", "precision", "recall", "f1", "roc_auc")
_CORE5: Final[set[str]] = {"random_forest", "extra_trees", "gradient_boosting", "svm", "knn"}
_CUT = 8


def _records(n_draws: int = 12) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(draw_number=n, numbers=(_NUMBERS[n % 3],)) for n in range(1, n_draws + 1)
    ]


def _feature_rows(records: list[SimpleNamespace]) -> list[object]:
    from backend.app.ml.feature_reader import FeatureValueRow

    return [
        FeatureValueRow(fid, draw.draw_number, float(draw.draw_number + j))
        for draw in records
        for j, fid in enumerate(ML_FEATURE_ORDER)
    ]


def _train(
    rows: list[SimpleNamespace],
    *,
    family: str = "random_forest",
    cut: int = _CUT,
    feature_rows: list[object] | None = None,
) -> object:
    from backend.app.ml.engine import MlEngine

    return MlEngine().train(
        family=family,
        lottery_id=7,
        records=rows,
        snapshot_id=1,
        cut=cut,
        feature_rows=feature_rows if feature_rows is not None else _feature_rows(rows),
    )


def test_engine_train_basic() -> None:
    """Fits core-5, returns metrics + trained models, and is deterministic (MLE-04)."""
    result = _train(_records())

    assert result.family == "random_forest"
    assert set(result.metrics) == set(_METRIC_NAMES)
    assert len(result.models) == len(_NUMBERS)
    assert all(isinstance(v, Decimal) for v in result.metrics.values())
    assert len(result.fingerprint) == 64 and len(result.checksum) == 64
    assert callable(result.models[_NUMBERS[0]].predict)

    second = _train(_records())
    assert (result.fingerprint, result.checksum, result.metrics) == (
        second.fingerprint,
        second.checksum,
        second.metrics,
    )
    assert (result.train_draws, result.eval_draws) == (second.train_draws, second.eval_draws)


def test_engine_uses_ml_feature_order() -> None:
    """X columns follow canonical ``ML_FEATURE_ORDER`` regardless of input row order."""
    from backend.app.ml.feature_reader import build_feature_matrix

    rows = _feature_rows(_records())
    shuffled = [rows[i] for i in random.Random(0).sample(range(len(rows)), len(rows))]
    assert _train(_records(), feature_rows=shuffled).features == ML_FEATURE_ORDER

    X, draw_numbers = build_feature_matrix(rows)
    assert X.shape == (len(_records()), len(ML_FEATURE_ORDER))
    assert draw_numbers == [d.draw_number for d in _records()]  # ascending, no shuffle


def test_engine_metrics_quantized() -> None:
    """Every metric value is a Decimal with Numeric(20,8) scale (no float leaks)."""
    result = _train(_records())

    for target, values in result.quantized.items():
        for name, value in values.items():
            assert value.as_tuple().exponent == -8, f"{target} {name} not 8-digit Decimal"
    assert all(result.metrics[name].as_tuple().exponent == -8 for name in _METRIC_NAMES)


def test_engine_no_future_models() -> None:
    """Only core-5 trains: future-ml families are declared but never fit (MLE-07)."""
    from backend.app.ml.engine import MlEngine

    engine = MlEngine()
    assert set(engine.registry) == _CORE5
    for future in FUTURE_ML_FAMILIES:
        assert future not in engine.registry
        with pytest.raises(ValueError):
            _train(_records(), family=future)


def test_engine_walk_forward_respects_cut() -> None:
    """``train <= cut < eval``: train draws never exceed the cut, eval draws always do."""
    result = _train(_records(), cut=_CUT)

    assert result.train_draws == (1, 2, 3, 4, 5, 6, 7, 8)
    assert result.eval_draws == (9, 10, 11)  # draw 12 has no n+1 target
    assert all(d <= _CUT for d in result.train_draws)
    assert all(d > _CUT for d in result.eval_draws)
    assert _train(_records(), cut=10).fingerprint != result.fingerprint  # cut in digest


def test_anti_shuffle_rejected() -> None:
    """A leaked eval-before-cut split raises ``LeakageError``; training is order-stable."""
    from backend.app.ml.splitter import LeakageError, validate_split, walk_forward_split

    train, eval_rows = walk_forward_split(_records()[:11], cut=_CUT)
    validate_split([r.draw_number for r in train], [r.draw_number for r in eval_rows], cut=_CUT)

    with pytest.raises(LeakageError):
        validate_split([1, 2, 3, 8, 9], [4, 5, 6, 7, 8], cut=_CUT)  # shuffled/leaked
    with pytest.raises(LeakageError):
        validate_split([1, 2, 3, 4], [4, 5, 6], cut=4)  # target draw duplicated into eval

    moved = _records()
    result_a, result_b = _train(_records()), _train([moved[0], *moved[2:], moved[1]])
    assert result_a.train_draws == result_b.train_draws  # splitter never shuffles (D2)
    assert result_a.checksum == result_b.checksum


def test_engine_snapshot_not_found() -> None:
    """A missing F4 snapshot surfaces SNAPSHOT_NOT_FOUND before any training (MLE-06)."""
    from backend.app.ml.engine import MlEngine
    from backend.app.services.errors import SnapshotNotFoundError

    with pytest.raises(SnapshotNotFoundError) as err:
        MlEngine().train(family="random_forest", lottery_id=7, records=_records(), snapshot_id=99)
    assert err.value.code == "SNAPSHOT_NOT_FOUND"
