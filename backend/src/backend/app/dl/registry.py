"""core-3 DL model registry — dict-dispatch, PyTorch only (DLE-07/11, D-A1).

One source of truth for the two executed families under ``model_set="core-3"``:
``build_dl_registry()`` exposes canonical full slugs (``mlp``, ``lstm``),
``CORE_3_MODELS`` keeps the PR1 short slugs.  Transformer/TensorFlow are
declared in ``FUTURE_DL_FAMILIES`` but NEVER imported here — the
dependency-gate tests assert their absence (DLE-07, D1).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

# core-3 scope identity (DLE-07): the ONLY executed model set in Fase 8.
MODEL_SET_CORE_3: Final[str] = "core-3"

# Future-DL families: versioned, declared, never scheduled (DLE-07).  Kept as
# literals so the banned-import scan can grep the module for import statements.
FUTURE_DL_FAMILIES: Final[tuple[str, ...]] = ("transformer", "tensorflow")

# Canonical core-3 definitions: (full slug, short slug, default params).
# Insertion order IS the canonical training order; default params are
# JSON-serializable (they feed the fingerprint and ``dl_metrics.params_json``).
_CORE_3_SOURCE: Final[tuple[tuple[str, str, dict[str, object]], ...]] = (
    (
        "mlp",
        "mlp",
        {
            "hidden_layers": [64, 32],
            "activation": "relu",
            "epochs": 50,
            "batch_size": 32,
            "lr": 1e-3,
        },
    ),
    (
        "lstm",
        "lstm",
        {
            "hidden_size": 64,
            "num_layers": 2,
            "dropout": 0.1,
            "epochs": 50,
            "batch_size": 32,
            "lr": 1e-3,
        },
    ),
)


def build_dl_registry() -> Mapping[str, dict[str, object]]:
    """Build the executed core-3 registry keyed by canonical full slug.

    Returns an immutable mapping slug -> default params dict.  Every call
    returns fresh param dicts, so callers can never mutate the source table.
    """
    return MappingProxyType({slug: dict(params) for slug, _, params in _CORE_3_SOURCE})


# PR1-compatible short-slug view of the same table (never drifts from the source).
CORE_3_MODELS: Final[Mapping[str, dict]] = MappingProxyType(
    {short: dict(params) for _, short, params in _CORE_3_SOURCE}
)

__all__ = [
    "MODEL_SET_CORE_3",
    "CORE_3_MODELS",
    "FUTURE_DL_FAMILIES",
    "build_dl_registry",
]
