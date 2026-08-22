"""Window builder for DL sequences (DLE-04).

Builds windows of W consecutive F4 feature vectors from ordered draws.  Each
window captures a ``(draw_number, feature_matrix)`` pair where the matrix has
shape ``(W, len(DL_FEATURE_ORDER))`` — one row per consecutive draw, one column
per persistable F4 feature in canonical order.  Windows are valid only when
``n >= W`` (the first W draws form the first window).  No padding is ever
applied; short histories raise ``ValueError`` before any training begins
(DLE-04).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.app.dl.providers import DrawRow, FeatureRow

# Persistable F4 feature order: the same 8 scalar-persistable ids as
# ML_FEATURE_ORDER (DLE-04/F12 parity), matching what feature_values stores.
DL_FEATURE_ORDER: tuple[str, ...] = (
    "consecutive_count",
    "draw_mean",
    "draw_range",
    "draw_sum",
    "low_high_ratio",
    "max_current_gap",
    "odd_even_ratio",
    "repeated_from_previous",
)

# Default and bounds for W (DLE-04).
DEFAULT_WINDOW: int = 10
MIN_WINDOW: int = 2
MAX_WINDOW: int = 20


@dataclass(frozen=True)
class Window:
    """One valid window of W consecutive draws with their feature matrix.

    ``draw_number`` is the LAST draw in the window (the most recent).
    ``feature_matrix`` has shape ``(W, len(DL_FEATURE_ORDER))`` — one row per
    consecutive draw in chronological order (oldest first).
    """

    draw_number: int
    feature_matrix: np.ndarray  # shape (W, F), dtype=float64

    @property
    def W(self) -> int:
        """Sequence length (number of draws in this window)."""
        return self.feature_matrix.shape[0]


def build_windows(
    draws: list[DrawRow],
    feature_rows: list[FeatureRow],
    *,
    W: int = DEFAULT_WINDOW,
) -> list[Window]:
    """Build all valid windows of W consecutive F4 vectors from ``draws``.

    Parameters
    ----------
    draws:
        Draws ordered by ``draw_number`` (ascending).
    feature_rows:
        F4 feature values for every draw in ``draws``.
    W:
        Window size (sequence length).  Must be in ``[MIN_WINDOW, MAX_WINDOW]``.

    Returns
    -------
    list[Window]
        Windows in chronological order.  Each window's ``draw_number`` is the
        last draw in that window.  The number of windows is
        ``max(0, len(draws) - W + 1)`` when ``len(draws) >= W``, else 0.

    Raises
    ------
    ValueError
        If ``W`` is out of bounds or ``len(draws) < W``.
    """
    if W < MIN_WINDOW or W > MAX_WINDOW:
        raise ValueError(f"W={W} out of bounds [{MIN_WINDOW}, {MAX_WINDOW}]")
    if len(draws) < W:
        raise ValueError(f"Need >= {W} draws for window, got {len(draws)}")

    # Index draws by draw_number (preserves ascending order).
    draw_numbers = [d.draw_number for d in draws]

    # Group feature rows by draw_number → {draw_number: {feature_id: value}}.
    features_by_draw: dict[int, dict[str, float]] = {}
    for row in feature_rows:
        features_by_draw.setdefault(row.draw_number, {})[row.feature_id] = row.value

    # Build windows: each window ends at draw_numbers[i] and spans i-W+1..i.
    windows: list[Window] = []
    for i in range(W - 1, len(draw_numbers)):
        end_idx = i
        start_idx = i - W + 1
        window_draw_numbers = draw_numbers[start_idx : end_idx + 1]

        # Build feature matrix (W rows, F columns) in canonical order.
        matrix = np.empty((W, len(DL_FEATURE_ORDER)), dtype=np.float64)
        for row_idx, dn in enumerate(window_draw_numbers):
            draw_features = features_by_draw.get(dn, {})
            for col_idx, feat_id in enumerate(DL_FEATURE_ORDER):
                matrix[row_idx, col_idx] = draw_features.get(feat_id, 0.0)

        windows.append(Window(draw_number=draw_numbers[end_idx], feature_matrix=matrix))

    return windows


__all__ = [
    "DEFAULT_WINDOW",
    "DL_FEATURE_ORDER",
    "MAX_WINDOW",
    "MIN_WINDOW",
    "Window",
    "build_windows",
]
