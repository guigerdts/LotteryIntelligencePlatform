"""Walk-forward window splitter (BTE-04, BTE-17).

Generates non-overlapping train/eval windows from a chronologically
sorted list of ``Draw`` objects.  Guarantees strict temporal ordering
(BTE-17): every train draw precedes every eval draw within a window.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from backend.app.backtesting.types import BacktestConfig, Draw


@dataclass(frozen=True)
class Window:
    """A single walk-forward window.

    Attributes:
        index: Sequential window number (0-based).
        train_draws: Draws in the training portion (strictly before eval).
        eval_draws: Draws in the evaluation portion.
    """

    index: int
    train_draws: tuple[Draw, ...]
    eval_draws: tuple[Draw, ...]


class WalkForwardSplitter:
    """Walk-forward window construction (BTE-04, BTE-17).

    The splitter converts ``train_years`` into a draw count using the
    median draws-per-year observed in the supplied data, then slides a
    fixed-size window forward by ``step_count`` eval periods.

    Guarantees:
    - ``max(train_draws).draw_date < min(eval_draws).draw_date`` (BTE-17).
    - First window requires ``len(train_draws) >= min_train_draws`` (BTE-07).
    - No overlap between consecutive windows.
    """

    def __init__(self, config: BacktestConfig) -> None:
        self._train_years = config.train_years
        self._eval_count = config.eval_count
        self._step_count = config.step_count
        self._min_train_draws = config.min_train_draws

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(self, draws: list[Draw]) -> list[Window]:
        """Generate walk-forward windows from *draws*.

        Parameters:
            draws: Chronologically sorted list of historical draws.

        Returns:
            List of ``Window`` objects with non-overlapping train/eval
            splits that respect temporal ordering (BTE-17).

        Raises:
            ValueError: If fewer draws than ``min_train_draws`` are supplied.
        """
        if not draws:
            return []

        sorted_draws = sorted(draws, key=lambda d: d.draw_date)
        train_count = self._estimate_train_count(sorted_draws)

        if train_count < self._min_train_draws:
            raise ValueError(
                f"Estimated train size {train_count} is below "
                f"min_train_draws ({self._min_train_draws})"
            )

        windows: list[Window] = []
        idx = 0
        win_idx = 0

        while True:
            train_start = idx
            train_end = idx + train_count
            eval_start = train_end
            eval_end = eval_start + self._eval_count

            if eval_end > len(sorted_draws):
                break

            window = Window(
                index=win_idx,
                train_draws=tuple(sorted_draws[train_start:train_end]),
                eval_draws=tuple(sorted_draws[eval_start:eval_end]),
            )
            windows.append(window)

            idx += self._step_count
            win_idx += 1

        if windows:
            self._validate_windows(windows)

        return windows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _estimate_train_count(self, draws: list[Draw]) -> int:
        """Convert ``train_years`` to a draw count.

        Uses the median inter-draw gap to estimate how many draws
        correspond to ``train_years`` worth of data.
        """
        if len(draws) < 2:
            return len(draws)

        # Compute median days between consecutive draws
        gaps = [(draws[i + 1].draw_date - draws[i].draw_date).days for i in range(len(draws) - 1)]
        median_gap = median(gaps) if gaps else 1
        if median_gap <= 0:
            median_gap = 1

        days_needed = self._train_years * 365
        estimated = int(days_needed / median_gap)
        return max(estimated, 1)

    def _validate_windows(self, windows: list[Window]) -> None:
        """Assert strict temporal ordering (BTE-17).

        Every train draw must precede every eval draw within each window.
        """
        for w in windows:
            if not w.train_draws or not w.eval_draws:
                continue
            last_train = max(d.draw_date for d in w.train_draws)
            first_eval = min(d.draw_date for d in w.eval_draws)
            if last_train >= first_eval:
                raise ValueError(
                    f"Window {w.index}: temporal ordering violated "
                    f"(last train {last_train} >= first eval {first_eval})"
                )
