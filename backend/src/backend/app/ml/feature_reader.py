"""Read-only F4 feature seam + design-matrix builder (MLE-03/05/06, M-A5).

Owns the ``FeatureValueRow`` carry and ``build_feature_matrix``, which enforces
the canonical ``ML_FEATURE_ORDER`` column order. The ``FeatureSnapshotReader``
Protocol lands with the provider seams in ``providers.py`` (PR4, MLE-06). A
missing feature/draw/snapshot raises ``SnapshotNotFoundError`` 404 before any
training — absence is never zero-guessed (MLE-06).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from backend.app.ml.features import ML_FEATURE_ORDER
from backend.app.services.errors import SnapshotNotFoundError


@dataclass(frozen=True, slots=True)
class FeatureValueRow:
    """One persisted ``(feature_id, draw_number, value)`` row of an F4 snapshot."""

    feature_id: str
    draw_number: int
    value: float


def build_feature_matrix(
    rows: Iterable[FeatureValueRow],
    *,
    feature_order: Sequence[str] = ML_FEATURE_ORDER,
) -> tuple[np.ndarray, list[int]]:
    """Design matrix ``X`` (rows = draws, cols = ``feature_order``) by ascending draw.

    Every draw must expose ALL ``feature_order`` ids else ``SnapshotNotFoundError``
    (MLE-06); never shuffles (D2).
    """
    by_draw: dict[int, dict[str, float]] = {}
    for row in rows:
        by_draw.setdefault(row.draw_number, {})[row.feature_id] = float(row.value)
    if not by_draw:
        raise SnapshotNotFoundError("no F4 feature snapshot rows")
    draw_numbers = sorted(by_draw)
    matrix = np.empty((len(draw_numbers), len(feature_order)), dtype=float)
    for i, draw in enumerate(draw_numbers):
        values = by_draw[draw]
        for j, feature_id in enumerate(feature_order):
            if feature_id not in values:
                raise SnapshotNotFoundError(
                    f"F4 snapshot missing feature {feature_id!r} at draw {draw}"
                )
            matrix[i, j] = values[feature_id]
    return matrix, draw_numbers


__all__ = ["FeatureValueRow", "build_feature_matrix"]
