"""Sequence builder for DL training (DLE-03/04/07).

Converts windows into model-ready tensors: ``X`` of shape
``(samples, W, F)`` as float32 (F = ``len(DL_FEATURE_ORDER)``), ``y`` of shape
``(samples, 10)`` as float32 binary (participation in draw ``n+1``; the 10 is
the fixture number universe, not the feature count).  Canonical feature order
matches ``DL_FEATURE_ORDER`` (F12 parity with ``ML_FEATURE_ORDER``).  No
shuffle, no source mutation (DLE-07).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.app.dl.providers import DrawRow
from backend.app.dl.window import DL_FEATURE_ORDER, Window


@dataclass(frozen=True)
class SequenceBatch:
    """One batch of DL training data.

    ``X``: shape ``(samples, W, F)``, float32, canonical feature order.
    ``y``: shape ``(samples, 10)``, float32 binary (1.0 = number present in n+1).
    ``draw_numbers``: the last draw_number in each window (for traceability).
    """

    X: np.ndarray  # shape (N, W, F), dtype=float32
    y: np.ndarray  # shape (N, 10), dtype=float32
    draw_numbers: list[int]


def build_tensors(
    windows: list[Window],
    draws: list[DrawRow],
) -> SequenceBatch:
    """Build training tensors from windows and draw data.

    For each window ending at draw_number ``dn``:
    - ``X[i]`` = the window's feature matrix cast to float32
    - ``y[i][j]`` = 1.0 if number ``j+1`` (1-indexed) appears in the draw
      at ``dn + 1``, else 0.0

    Parameters
    ----------
    windows:
        Validated windows (post-splitter, chronological).
    draws:
        All draws (for target lookup).  Must include the draw AFTER each
        window's last draw (for target computation).

    Returns
    -------
    SequenceBatch
        Tensors ready for DL training.

    Raises
    ------
    ValueError
        If a window's target draw (``draw_number + 1``) is missing from
        ``draws``.
    """
    if not windows:
        return SequenceBatch(
            X=np.empty((0, 0, len(DL_FEATURE_ORDER)), dtype=np.float32),
            y=np.empty((0, 10), dtype=np.float32),
            draw_numbers=[],
        )

    # Index draws by draw_number for target lookup.
    draws_by_num = {d.draw_number: d for d in draws}

    W = windows[0].W
    F = len(DL_FEATURE_ORDER)
    N = len(windows)

    X = np.empty((N, W, F), dtype=np.float32)
    y = np.empty((N, 10), dtype=np.float32)
    draw_numbers: list[int] = []

    for i, window in enumerate(windows):
        # Feature matrix → float32 (D-A8).
        X[i] = window.feature_matrix.astype(np.float32)

        # Target: participation in draw n+1.
        target_draw_num = window.draw_number + 1
        target_draw = draws_by_num.get(target_draw_num)
        if target_draw is None:
            raise ValueError(
                f"Target draw {target_draw_num} not found for window ending at {window.draw_number}"
            )

        # Binary participation: 1.0 if number (1-indexed) is in the draw.
        for j in range(10):
            y[i, j] = 1.0 if (j + 1) in target_draw.numbers else 0.0

        draw_numbers.append(window.draw_number)

    return SequenceBatch(X=X, y=y, draw_numbers=draw_numbers)


__all__ = ["SequenceBatch", "build_tensors"]
