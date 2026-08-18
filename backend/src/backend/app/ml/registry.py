"""core-5 model registry — dict-dispatch, scikit-learn only (MLE-04/MLE-07, M-A2).

One source of truth for the five executed families under ``model_set="core-5"``:
``build_ml_registry()`` exposes canonical full slugs (``random_forest``,
``extra_trees``, ``gradient_boosting``, ``svm``, ``knn``), ``CORE_5_MODELS``
keeps the PR1 short slugs, ``random_state=0`` fixed wherever supported (D2).
XGBoost/LightGBM/CatBoost are declared in ``FUTURE_ML_FAMILIES`` but NEVER imported
here — the dependency-gate tests assert their absence (MLE-07, D1, M-A9).

Estimator classes resolve lazily (inside ``build_ml_registry`` / ``CORE_5_MODELS``)
so scikit-learn is not imported at cold start (DLE-17/PFM-06).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

# core-5 scope identity (MLE-07): the ONLY executed model set in Fase 7.
MODEL_SET_CORE_5: Final[str] = "core-5"

# Future-ml families: versioned, declared, never scheduled (MLE-07). Kept as
# literals so the banned-import scan can grep the module for import statements.
FUTURE_ML_FAMILIES: Final[tuple[str, ...]] = ("xgboost", "lightgbm", "catboost")

# Canonical core-5 specs: (full slug, short PR1 id, default params). Insertion
# order IS the canonical training order; default params are JSON-serializable
# (they feed the fingerprint and ``ml_metrics.params_json``).
_CORE_5_SPECS: Final[tuple[tuple[str, str, dict[str, object]], ...]] = (
    ("random_forest", "rf", {"random_state": 0, "n_estimators": 100}),
    ("extra_trees", "et", {"random_state": 0, "n_estimators": 100}),
    ("gradient_boosting", "gb", {"random_state": 0}),
    ("svm", "svm", {"random_state": 0}),
    ("knn", "knn", {"n_neighbors": 5}),
)


def _estimator_classes() -> dict[str, type]:
    """Resolve sklearn estimator classes on first use (deferred import)."""
    from sklearn.ensemble import (  # noqa: PLC0415  # deferred: DLE-17
        ExtraTreesClassifier,
        GradientBoostingClassifier,
        RandomForestClassifier,
    )
    from sklearn.neighbors import KNeighborsClassifier  # noqa: PLC0415
    from sklearn.svm import SVC  # noqa: PLC0415

    return {
        "random_forest": RandomForestClassifier,
        "extra_trees": ExtraTreesClassifier,
        "gradient_boosting": GradientBoostingClassifier,
        "svm": SVC,
        "knn": KNeighborsClassifier,
    }


def build_ml_registry() -> Mapping[str, tuple[type, dict[str, object]]]:
    """Build the executed core-5 registry keyed by canonical full slug.

    Returns an immutable mapping slug -> (estimator class, default params). Every
    call returns fresh param dicts, so callers can never mutate the source table.
    """
    classes = _estimator_classes()
    return MappingProxyType(
        {slug: (classes[slug], dict(params)) for slug, _, params in _CORE_5_SPECS}
    )


class _LazyCore5Models(Mapping):
    """PR1-compatible short-slug view; classes resolve on first access (M-A2).

    Keeps ``CORE_5_MODELS`` a module-level mapping (existing test contract) while
    deferring the sklearn import until the first actual access.
    """

    def _build(self) -> Mapping[str, tuple[type, dict]]:
        classes = _estimator_classes()
        return MappingProxyType(
            {short: (classes[slug], dict(params)) for slug, short, params in _CORE_5_SPECS}
        )

    def __getitem__(self, key: str) -> tuple[type, dict]:
        return self._build()[key]

    def __iter__(self):
        return iter(self._build())

    def __len__(self) -> int:
        return len(self._build())


CORE_5_MODELS: Mapping[str, tuple[type, dict]] = _LazyCore5Models()

__all__ = ["MODEL_SET_CORE_5", "CORE_5_MODELS", "FUTURE_ML_FAMILIES", "build_ml_registry"]
