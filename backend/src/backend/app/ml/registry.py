"""core-5 model registry — dict-dispatch, scikit-learn only (MLE-04/MLE-07, M-A2).

One source of truth for the five executed families under ``model_set="core-5"``:
``build_ml_registry()`` exposes canonical full slugs (``random_forest``,
``extra_trees``, ``gradient_boosting``, ``svm``, ``knn``), ``CORE_5_MODELS``
keeps the PR1 short slugs, ``random_state=0`` fixed wherever supported (D2).
XGBoost/LightGBM/CatBoost are declared in ``FUTURE_ML_FAMILIES`` but NEVER imported
here — the dependency-gate tests assert their absence (MLE-07, D1, M-A9).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC

# core-5 scope identity (MLE-07): the ONLY executed model set in Fase 7.
MODEL_SET_CORE_5: Final[str] = "core-5"

# Future-ml families: versioned, declared, never scheduled (MLE-07). Kept as
# literals so the banned-import scan can grep the module for import statements.
FUTURE_ML_FAMILIES: Final[tuple[str, ...]] = ("xgboost", "lightgbm", "catboost")

# Canonical core-5 definitions: (full slug, short PR1 id, estimator class, default
# params). Insertion order IS the canonical training order; default params are
# JSON-serializable (they feed the fingerprint and ``ml_metrics.params_json``).
_CORE_5_SOURCE: Final[tuple[tuple[str, str, type, dict[str, object]], ...]] = (
    ("random_forest", "rf", RandomForestClassifier, {"random_state": 0, "n_estimators": 100}),
    ("extra_trees", "et", ExtraTreesClassifier, {"random_state": 0, "n_estimators": 100}),
    ("gradient_boosting", "gb", GradientBoostingClassifier, {"random_state": 0}),
    ("svm", "svm", SVC, {"random_state": 0}),
    ("knn", "knn", KNeighborsClassifier, {"n_neighbors": 5}),
)


def build_ml_registry() -> Mapping[str, tuple[type, dict[str, object]]]:
    """Build the executed core-5 registry keyed by canonical full slug.

    Returns an immutable mapping slug -> (estimator class, default params). Every
    call returns fresh param dicts, so callers can never mutate the source table.
    """
    return MappingProxyType(
        {slug: (estimator, dict(params)) for slug, _, estimator, params in _CORE_5_SOURCE}
    )


# PR1-compatible short-slug view of the same table (never drifts from the source).
CORE_5_MODELS: Final[Mapping[str, tuple[type, dict]]] = MappingProxyType(
    {short: (estimator, dict(params)) for _, short, estimator, params in _CORE_5_SOURCE}
)

__all__ = ["MODEL_SET_CORE_5", "CORE_5_MODELS", "FUTURE_ML_FAMILIES", "build_ml_registry"]
