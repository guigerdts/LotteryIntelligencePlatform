"""Unit tests for dl.sequence_builder — tensor construction (DLE-03/04/07)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.dl.providers import DrawRow
from backend.app.dl.sequence_builder import build_tensors
from backend.app.dl.window import DL_FEATURE_ORDER, Window


def _window(draw_number: int, W: int = 10) -> Window:
    """Create a Window with deterministic feature values."""
    matrix = np.full((W, len(DL_FEATURE_ORDER)), float(draw_number) * 0.01)
    return Window(draw_number=draw_number, feature_matrix=matrix)


def _draw(draw_number: int, numbers: tuple[int, ...] = (1, 2, 3)) -> DrawRow:
    """Create a DrawRow."""
    return DrawRow(draw_number=draw_number, numbers=numbers)


def test_build_tensors_empty_windows() -> None:
    """Empty windows produce empty tensors."""
    batch = build_tensors([], [_draw(1)])
    assert batch.X.shape == (0, 0, 10)
    assert batch.y.shape == (0, 10)
    assert batch.draw_numbers == []


def test_build_tensors_shape() -> None:
    """Output tensors have correct shape."""
    windows = [_window(d, W=3) for d in [3, 4, 5]]
    draws = [_draw(d) for d in range(1, 7)]
    batch = build_tensors(windows, draws)
    assert batch.X.shape == (3, 3, 10)
    assert batch.y.shape == (3, 10)


def test_build_tensors_dtype() -> None:
    """Output tensors are float32 (D-A8)."""
    windows = [_window(d, W=3) for d in [3, 4, 5]]
    draws = [_draw(d) for d in range(1, 7)]
    batch = build_tensors(windows, draws)
    assert batch.X.dtype == np.float32
    assert batch.y.dtype == np.float32


def test_build_tensors_target_binary() -> None:
    """Target is binary: 1.0 if number in draw n+1, else 0.0."""
    windows = [_window(3, W=2)]
    # Draw 4 (target) contains numbers (1, 3, 5)
    draws = [_draw(4, numbers=(1, 3, 5))]
    batch = build_tensors(windows, draws)
    # Numbers 1-indexed: 1→index 0, 3→index 2, 5→index 4
    assert batch.y[0, 0] == 1.0  # number 1
    assert batch.y[0, 1] == 0.0  # number 2
    assert batch.y[0, 2] == 1.0  # number 3
    assert batch.y[0, 3] == 0.0  # number 4
    assert batch.y[0, 4] == 1.0  # number 5


def test_build_tensors_target_missing_draw() -> None:
    """Missing target draw raises ValueError."""
    windows = [_window(10, W=3)]
    draws = [_draw(1), _draw(2)]  # no draw 11
    with pytest.raises(ValueError, match="Target draw 11 not found"):
        build_tensors(windows, draws)


def test_build_tensors_draw_numbers() -> None:
    """draw_numbers match window draw_numbers."""
    windows = [_window(d, W=2) for d in [5, 6, 7]]
    draws = [_draw(d) for d in range(4, 9)]
    batch = build_tensors(windows, draws)
    assert batch.draw_numbers == [5, 6, 7]


def test_build_tensors_no_shuffle() -> None:
    """Output order matches input window order."""
    windows = [_window(d, W=2) for d in [3, 4, 5]]
    draws = [_draw(d) for d in range(2, 7)]
    batch = build_tensors(windows, draws)
    # Feature values: window 3 → 0.03, window 4 → 0.04, window 5 → 0.05
    assert batch.X[0, 0, 0] == pytest.approx(0.03, abs=1e-6)
    assert batch.X[1, 0, 0] == pytest.approx(0.04, abs=1e-6)
    assert batch.X[2, 0, 0] == pytest.approx(0.05, abs=1e-6)


def test_build_tensors_source_unchanged() -> None:
    """Input windows and draws are not mutated."""
    matrix = np.ones((3, 10), dtype=np.float64)
    window = Window(draw_number=5, feature_matrix=matrix)
    draw = _draw(6, numbers=(1, 2, 3))
    _ = build_tensors([window], [draw])
    assert window.feature_matrix is matrix  # identity preserved
    assert draw.numbers == (1, 2, 3)


def test_build_tensors_all_numbers_participate() -> None:
    """All 10 numbers present in target draw → all 1.0."""
    windows = [_window(5, W=2)]
    draws = [_draw(6, numbers=tuple(range(1, 11)))]
    batch = build_tensors(windows, draws)
    assert np.all(batch.y[0] == 1.0)


def test_build_tensors_no_numbers_participate() -> None:
    """No numbers present → all 0.0."""
    windows = [_window(5, W=2)]
    draws = [_draw(6, numbers=())]
    batch = build_tensors(windows, draws)
    assert np.all(batch.y[0] == 0.0)
