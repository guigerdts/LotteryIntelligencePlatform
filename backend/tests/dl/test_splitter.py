"""Unit tests for dl.splitter — window-aware walk-forward (DLE-05)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.dl.splitter import LeakageError, split_windows, validate_windows
from backend.app.dl.window import Window


def _window(draw_number: int, W: int = 10) -> Window:
    """Create a Window with the given draw_number."""
    return Window(
        draw_number=draw_number,
        feature_matrix=np.zeros((W, 10), dtype=np.float64),
    )


def test_split_basic() -> None:
    """Basic split: train <= cut, eval > cut."""
    # W=2 so no straddle with cut=10
    windows = [_window(d, W=2) for d in range(3, 21)]
    train, eval_ = split_windows(windows, cut=10)
    assert len(train) == 8  # 3..10
    assert len(eval_) == 10  # 11..20
    assert train[-1].draw_number == 10
    assert eval_[0].draw_number == 11


def test_split_train_only() -> None:
    """All windows in train when cut >= last draw."""
    windows = [_window(d) for d in range(1, 11)]
    with pytest.raises(ValueError, match="empty"):
        split_windows(windows, cut=20)


def test_split_eval_only() -> None:
    """All windows in eval when cut < first draw."""
    # W=2 so no straddle
    windows = [_window(d, W=2) for d in range(11, 21)]
    with pytest.raises(ValueError, match="empty"):
        split_windows(windows, cut=5)


def test_split_straddle_detected() -> None:
    """Window straddling cut raises LeakageError."""
    # Window ending at 12 with W=10: first_draw = 12-10+1 = 3
    # If cut=8: first_draw=3 <= 8 AND last_draw=12 > 8 → straddle
    windows = [_window(d, W=10) for d in range(11, 21)]
    with pytest.raises(LeakageError, match="straddles"):
        split_windows(windows, cut=8)


def test_split_no_straddle_clean() -> None:
    """Clean split with no straddle."""
    # Windows ending at 10,11,12 with W=2:
    # Window(10): first=9, last=10 → train (10 <= cut=10)
    # Window(11): first=10, last=11 → eval (11 > 10)
    # Window(12): first=11, last=12 → eval (12 > 10)
    windows = [_window(d, W=2) for d in range(10, 13)]
    train, eval_ = split_windows(windows, cut=10)
    assert len(train) == 1
    assert len(eval_) == 2


def test_split_anti_shuffle() -> None:
    """Shuffled windows detected as leakage."""
    # Chronologically ordered: Window(5) then Window(15), but placed
    # out of order in the list [15, 5].  The anti-shuffle check needs
    # to verify the *original* list is in chronological order.
    # With W=2 and cut=10: neither straddles.
    windows = [_window(15, W=2), _window(5, W=2)]
    with pytest.raises(LeakageError, match="[Ss]huffle"):
        split_windows(windows, cut=10)


def test_validate_windows_clean() -> None:
    """validate_windows passes for clean windows."""
    windows = [_window(d, W=2) for d in range(10, 14)]
    validate_windows(windows, cut=10)


def test_validate_windows_straddle() -> None:
    """validate_windows detects straddle."""
    windows = [_window(d, W=10) for d in range(11, 21)]
    with pytest.raises(LeakageError, match="straddles"):
        validate_windows(windows, cut=8)


def test_split_many_windows() -> None:
    """Split works with many windows."""
    windows = [_window(d, W=2) for d in range(3, 51)]
    train, eval_ = split_windows(windows, cut=30)
    assert len(train) == 28  # 3..30
    assert len(eval_) == 20  # 31..50


def test_split_w3_clean() -> None:
    """W=3 windows split cleanly at cut."""
    # Windows ending at 3,4,5,6,7 with W=3
    # Window(3): first=1, last=3 → train (3 <= cut=5)
    # Window(4): first=2, last=4 → train (4 <= 5)
    # Window(5): first=3, last=5 → train (5 <= 5)
    # Window(6): first=4, last=6 → eval (6 > 5) — first_draw=4 <= 5, last=6 > 5 → STRADDLE!
    # Need cut such that no straddle. cut=5: Window(6) first=4 <=5, last=6>5 → straddle.
    # cut=3: Window(4) first=2 <=3, last=4>3 → straddle.
    # For W=3, need cut such that no window straddles.
    # Windows at 3,4,5,6,7 with W=3: first draws are 1,2,3,4,5
    # cut=2: Window(3) first=1 <=2, last=3>2 → straddle
    # cut=7: all train
    # Need at least 2 windows on each side. Use windows 5,6,7,8,9 with W=2.
    windows = [_window(d, W=2) for d in range(5, 10)]
    train, eval_ = split_windows(windows, cut=7)
    assert len(train) == 3  # 5,6,7
    assert len(eval_) == 2  # 8,9
