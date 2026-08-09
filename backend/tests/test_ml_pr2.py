"""PR2 gates for Fase 7 ML: registry builder, fingerprint, determinism, walk-split.

Pins the PR2 slice: ``build_ml_registry()`` exposes exactly the 5 core-5 families
with no future-ml imports (MLE-04/07); ``FUTURE_ML_FAMILIES`` declares exactly 3,
never executed (MLE-07); ``compute_ml_fingerprint`` is canonical SHA-256 over
{data_hash, params, generator_version, cut} — key-order independent, cut/params
sensitive (MLE-05/D2); every metric is Decimal-quantized before any checksum, raw
floats never feed a digest (D2/D4); ``walk_forward_split`` is deterministic
(train ``<= cut``, eval ``> cut`` — design MLE-03 semantics) and rejects an
unusable cut with ValueError (MLE-03).
"""

from __future__ import annotations

import inspect
import re
from decimal import Decimal
from types import SimpleNamespace
from typing import Final

import pytest

FUTURE_ML_NAMES: Final[tuple[str, ...]] = ("xgboost", "lightgbm", "catboost", "networkx")

# Registry slugs the PR2 builder must expose (orchestrator PR2 scope list).
CORE_5_SLUGS: Final[tuple[str, ...]] = (
    "random_forest",
    "extra_trees",
    "gradient_boosting",
    "svm",
    "knn",
)


def _draw(draw_number: int) -> SimpleNamespace:
    """A minimal record carrying only ``draw_number`` for splitter fixtures."""
    return SimpleNamespace(draw_number=draw_number)


def _base_args() -> tuple[str, dict[str, int], str, int]:
    """Standard inputs for fingerprint tests (data_hash, params, version, cut)."""
    return ("a" * 64, {"random_state": 0, "n_estimators": 100}, "1.0.0", 80)


# ---------------------------------------------------------------------------
# T-08: registry builder + future-ml isolation
# ---------------------------------------------------------------------------


def test_registry_has_5_models() -> None:
    """``build_ml_registry()`` returns exactly the 5 core-5 families (MLE-07)."""
    from backend.app.ml.registry import build_ml_registry

    registry = build_ml_registry()
    assert len(registry) == 5
    # The full canonical slug set participates in fingerprints/params later.
    assert set(registry) == set(CORE_5_SLUGS)
    for slug, (estimator, params) in registry.items():
        assert callable(estimator), f"{slug} must map to an estimator class"
        assert isinstance(params, dict) and params, f"{slug} must carry default params"
        # Defaults must stay JSON-serializable (fingerprint/params_json contract).
        assert all(isinstance(v, (int, float, str, bool)) for v in params.values())


def test_registry_no_future_imports() -> None:
    """``ml/registry.py`` never imports the future-ml libraries (MLE-04/D1)."""
    import backend.app.ml.registry as registry

    source = inspect.getsource(registry)
    imported = re.findall(r"^\s*(?:import|from)\s+([a-z_]+)", source, flags=re.MULTILINE)
    assert imported, "registry module must import at least sklearn"
    assert not any(name in FUTURE_ML_NAMES for name in imported), (
        f"banned imports present: {[n for n in imported if n in FUTURE_ML_NAMES]}"
    )


def test_future_families_declared() -> None:
    """``FUTURE_ML_FAMILIES`` declares exactly 3 families, never executed (MLE-07)."""
    from backend.app.ml.registry import FUTURE_ML_FAMILIES

    assert isinstance(FUTURE_ML_FAMILIES, tuple)
    assert FUTURE_ML_FAMILIES == ("xgboost", "lightgbm", "catboost")


# ---------------------------------------------------------------------------
# T_fp: canonical fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_canonical() -> None:
    """Equal inputs (any param key order, any dict order) yield identical hex."""
    from backend.app.ml.fingerprint import compute_ml_fingerprint

    data_hash = "aa" * 32
    params_a = {"n_estimators": 100, "random_state": 0}
    params_b = {"random_state": 0, "n_estimators": 100}  # insertion order differs
    kwargs = dict(params=params_a, generator_version="1.0.0", cut=80)

    assert compute_ml_fingerprint(data_hash, **kwargs) == compute_ml_fingerprint(
        data_hash, **kwargs
    )
    assert len(compute_ml_fingerprint(data_hash, **kwargs)) == 64
    # Canonical JSON is key-order-independent at every nesting level.
    assert compute_ml_fingerprint(
        data_hash, params=params_b, generator_version="1.0.0", cut=80
    ) == (compute_ml_fingerprint(data_hash, **kwargs))


def test_fingerprint_changes_on_cut() -> None:
    """A different ``cut`` MUST yield a different fingerprint (new version)."""
    from backend.app.ml.fingerprint import compute_ml_fingerprint

    data_hash, params, version, _ = _base_args()
    assert compute_ml_fingerprint(data_hash, params, version, cut=80) != compute_ml_fingerprint(
        data_hash, params, version, cut=81
    )


def test_fingerprint_changes_on_params() -> None:
    """A different hyperparameter set MUST yield a different fingerprint."""
    from backend.app.ml.fingerprint import compute_ml_fingerprint

    data_hash, _, version, cut = _base_args()
    base_params = {"random_state": 0, "n_estimators": 100}
    changed_params = {"random_state": 0, "n_estimators": 200}
    assert compute_ml_fingerprint(data_hash, base_params, version, cut) != compute_ml_fingerprint(
        data_hash, changed_params, version, cut
    )


# ---------------------------------------------------------------------------
# T_det: quantization + metrics checksum
# ---------------------------------------------------------------------------


def test_quantize_metric() -> None:
    """``quantize_metric`` rounds any float to a Decimal with 8 fraction digits."""
    from backend.app.ml.determinism import QUANTIZE_PRECISION, quantize_metric

    assert QUANTIZE_PRECISION == 8
    assert quantize_metric(3.14159) == Decimal("3.14159000")
    assert str(quantize_metric(3.14159)) == "3.14159000"
    assert str(quantize_metric(2.5)) == "2.50000000"  # triangulation: different path


def test_compute_metrics_checksum_deterministic() -> None:
    """Same quantized inputs => same hex checksum (byte-identical, D2)."""
    from backend.app.ml.determinism import compute_metrics_checksum

    metrics = {"accuracy": 0.8075, "f1": 0.75, "roc_auc": 0.66666666}
    assert compute_metrics_checksum(metrics) == compute_metrics_checksum(metrics)
    assert isinstance(compute_metrics_checksum(metrics), str)
    assert len(compute_metrics_checksum(metrics)) == 64


def test_compute_metrics_checksum_changes_on_value() -> None:
    """A raw metric change that survives quantization alters the checksum."""
    from backend.app.ml.determinism import compute_metrics_checksum

    base = {"accuracy": 0.80, "f1": 0.75}
    changed = {"accuracy": 0.81, "f1": 0.75}
    assert compute_metrics_checksum(base) != compute_metrics_checksum(changed)


# ---------------------------------------------------------------------------
# T_split: walk-forward splitter
# ---------------------------------------------------------------------------


def test_walk_forward_split_basic() -> None:
    """Train holds every record with draw_number <= cut; eval holds > cut (design MLE-03)."""
    from backend.app.ml.splitter import walk_forward_split

    records = [_draw(n) for n in range(1, 11)]
    train, eval_rows = walk_forward_split(records, cut=8)

    assert [r.draw_number for r in train] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [r.draw_number for r in eval_rows] == [9, 10]
    assert not any(r.draw_number in {r2.draw_number for r2 in eval_rows} for r in train)


def test_walk_forward_split_raises_on_bad_cut() -> None:
    """A cut that yields an empty train or eval side raises ValueError."""
    from backend.app.ml.splitter import walk_forward_split

    records = [_draw(n) for n in range(1, 11)]
    with pytest.raises(ValueError):
        walk_forward_split(records, cut=0)  # empty train side (no draw <= 0)
    with pytest.raises(ValueError):
        walk_forward_split(records, cut=10)  # empty eval side (no draw > 10)


def test_walk_forward_no_shuffle() -> None:
    """Repeated splits are deterministic: same drawn-numbers, same order (D2)."""
    from backend.app.ml.splitter import walk_forward_split

    records = [_draw(n) for n in range(1, 11)]
    first = walk_forward_split(records, cut=8)
    second = walk_forward_split(records, cut=8)

    assert first == second
    assert [r.draw_number for r in first[0]] == [1, 2, 3, 4, 5, 6, 7, 8]
