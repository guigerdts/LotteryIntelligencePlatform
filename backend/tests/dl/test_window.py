"""Unit tests for dl.window — WindowBuilder (DLE-04)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.dl.providers import DrawRow, FeatureRow
from backend.app.dl.window import (
    DL_FEATURE_ORDER,
    Window,
    build_windows,
)


def _make_draws(start: int, count: int) -> list[DrawRow]:
    """Create ``count`` draws starting at ``start``."""
    return [DrawRow(draw_number=start + i, numbers=(1, 2, 3)) for i in range(count)]


def _make_features(
    draws: list[DrawRow],
    feature_ids: tuple[str, ...] = DL_FEATURE_ORDER,
) -> list[FeatureRow]:
    """Create feature rows for all draws with value = draw_number * 0.01."""
    rows = []
    for d in draws:
        for idx, fid in enumerate(feature_ids):
            rows.append(
                FeatureRow(
                    feature_id=fid,
                    draw_number=d.draw_number,
                    value=float(d.draw_number) * 0.01 + idx * 0.001,
                )
            )
    return rows


def test_window_frozen() -> None:
    """Window is immutable (frozen dataclass)."""
    matrix = np.zeros((10, 10), dtype=np.float64)
    w = Window(draw_number=10, feature_matrix=matrix)
    assert w.draw_number == 10
    assert w.W == 10
    with pytest.raises(AttributeError):
        w.draw_number = 11  # type: ignore[misc]


def test_build_windows_basic() -> None:
    """build_windows produces correct number of windows."""
    draws = _make_draws(1, 15)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=10)
    assert len(windows) == 6  # 15 - 10 + 1 = 6


def test_build_windows_first_draw_number() -> None:
    """First window's draw_number is the W-th draw."""
    draws = _make_draws(1, 15)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=10)
    assert windows[0].draw_number == 10


def test_build_windows_last_draw_number() -> None:
    """Last window's draw_number is the last draw."""
    draws = _make_draws(1, 15)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=10)
    assert windows[-1].draw_number == 15


def test_build_windows_feature_shape() -> None:
    """Feature matrix has shape (W, 10)."""
    draws = _make_draws(1, 15)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=10)
    for w in windows:
        assert w.feature_matrix.shape == (10, 10)


def test_build_windows_canonical_order() -> None:
    """Features are in canonical DL_FEATURE_ORDER."""
    assert len(DL_FEATURE_ORDER) == 10
    assert DL_FEATURE_ORDER == (
        "consecutive_count",
        "current_frequency",
        "decade_distribution",
        "draw_mean",
        "draw_range",
        "draw_sum",
        "low_high_ratio",
        "max_current_gap",
        "odd_even_ratio",
        "repeated_from_previous",
    )


def test_build_windows_no_padding() -> None:
    """Windows contain exactly W draws, no padding."""
    draws = _make_draws(1, 12)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=5)
    for w in windows:
        assert w.W == 5


def test_build_windows_w_too_small() -> None:
    """W < MIN_WINDOW raises ValueError."""
    draws = _make_draws(1, 15)
    features = _make_features(draws)
    with pytest.raises(ValueError, match="out of bounds"):
        build_windows(draws, features, W=1)


def test_build_windows_w_too_large() -> None:
    """W > MAX_WINDOW raises ValueError."""
    draws = _make_draws(1, 15)
    features = _make_features(draws)
    with pytest.raises(ValueError, match="out of bounds"):
        build_windows(draws, features, W=25)


def test_build_windows_insufficient_draws() -> None:
    """Fewer draws than W raises ValueError."""
    draws = _make_draws(1, 5)
    features = _make_features(draws)
    with pytest.raises(ValueError, match="Need >= 10 draws"):
        build_windows(draws, features, W=10)


def test_build_windows_exact_w_draws() -> None:
    """Exactly W draws produces 1 window."""
    draws = _make_draws(1, 10)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=10)
    assert len(windows) == 1
    assert windows[0].draw_number == 10


def test_build_windows_w2() -> None:
    """W=2 produces N-1 windows."""
    draws = _make_draws(1, 10)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=2)
    assert len(windows) == 9


def test_build_windows_values_correct() -> None:
    """Feature matrix values match the input feature rows."""
    draws = _make_draws(1, 12)
    features = _make_features(draws)
    windows = build_windows(draws, features, W=3)
    # First window ends at draw 3, spans draws 1,2,3
    w = windows[0]
    assert w.draw_number == 3
    for row_idx, dn in enumerate([1, 2, 3]):
        expected = float(dn) * 0.01
        assert w.feature_matrix[row_idx, 0] == pytest.approx(expected, abs=1e-6)


def test_build_windows_empty_features() -> None:
    """Missing feature rows produce zeros in the matrix."""
    draws = _make_draws(1, 12)
    # No feature rows at all
    windows = build_windows(draws, [], W=3)
    assert len(windows) == 10
    assert np.all(windows[0].feature_matrix == 0.0)
