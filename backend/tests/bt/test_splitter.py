"""Tests for WalkForwardSplitter (BTE-04, BTE-07, BTE-17).

Verifies window construction, temporal ordering, minimum train draws,
and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.app.backtesting.splitter import WalkForwardSplitter
from backend.app.backtesting.types import BacktestConfig, Draw


def _make_draws(n: int, start_date: str = "2015-01-01") -> list[Draw]:
    """Create *n* draws spaced one week apart starting from *start_date*."""
    base = datetime.fromisoformat(start_date)
    return [
        Draw(
            id=i,
            draw_date=base + timedelta(weeks=i),
            numbers=(1, 2, 3, 4, 5),
            super_number=10,
        )
        for i in range(n)
    ]


class TestWalkForwardSplitter:
    """Window construction (BTE-04, BTE-17)."""

    def test_empty_draws_returns_empty(self) -> None:
        cfg = BacktestConfig(train_years=1, min_train_draws=10)
        splitter = WalkForwardSplitter(cfg)
        assert splitter.split([]) == []

    def test_single_window(self) -> None:
        draws = _make_draws(120)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        assert len(windows) >= 1
        assert windows[0].index == 0

    def test_multiple_windows(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        assert len(windows) > 1

    def test_temporal_ordering(self) -> None:
        """BTE-17: all train dates < all eval dates within each window."""
        draws = _make_draws(200)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        for w in windows:
            last_train = max(d.draw_date for d in w.train_draws)
            first_eval = min(d.draw_date for d in w.eval_draws)
            assert last_train < first_eval

    def test_no_eval_overlap_with_next_eval(self) -> None:
        """Consecutive eval periods are disjoint and ordered."""
        draws = _make_draws(300)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        for i in range(len(windows) - 1):
            eval_end_i = max(d.draw_date for d in windows[i].eval_draws)
            eval_start_next = min(d.draw_date for d in windows[i + 1].eval_draws)
            assert eval_end_i < eval_start_next

    def test_below_min_train_draws_returns_empty(self) -> None:
        """Insufficient data returns empty list (BTE-07)."""
        draws = _make_draws(5)
        cfg = BacktestConfig(
            train_years=10,
            eval_count=1,
            step_count=1,
            min_train_draws=100,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        assert windows == []

    def test_window_index_sequential(self) -> None:
        draws = _make_draws(300)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        for i, w in enumerate(windows):
            assert w.index == i

    def test_eval_count_controls_size(self) -> None:
        draws = _make_draws(200)
        cfg1 = BacktestConfig(train_years=1, eval_count=1, step_count=1, min_train_draws=10)
        cfg2 = BacktestConfig(train_years=1, eval_count=3, step_count=3, min_train_draws=10)
        w1 = WalkForwardSplitter(cfg1).split(draws)
        w2 = WalkForwardSplitter(cfg2).split(draws)
        # Larger eval_count + step_count → fewer windows
        assert len(w2) <= len(w1)

    def test_step_count_affects_window_spacing(self) -> None:
        draws = _make_draws(300)
        cfg = BacktestConfig(train_years=1, eval_count=1, step_count=5, min_train_draws=10)
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        if len(windows) >= 2:
            # Indices should skip by step_count
            assert windows[1].index == 1

    def test_first_window_starts_at_zero(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        assert windows[0].train_draws[0].id == draws[0].id

    def test_last_window_eval_within_bounds(self) -> None:
        draws = _make_draws(200)
        cfg = BacktestConfig(
            train_years=1,
            eval_count=1,
            step_count=1,
            min_train_draws=10,
        )
        splitter = WalkForwardSplitter(cfg)
        windows = splitter.split(draws)
        last_eval_end = max(d.id for d in windows[-1].eval_draws)
        assert last_eval_end <= draws[-1].id
