"""S3 parity tests: serial == parallel byte-identical (GF-1, PFM-01).

Verifies that ``ProcessPoolExecutor`` window parallelization produces
identical ``fingerprint``, ``aggregate_metrics``, and ``window_history``
for the same inputs (T-S3-04).  The module-level ``_evaluate_window``
worker builds per-window ``random.Random(config.seed + window_index)``
sub-seeds so every window is a pure deterministic function of its index.
"""

from __future__ import annotations

import inspect
import pickle
from datetime import datetime, timedelta
from typing import Any

from backend.app.backtesting.engine import BacktestEngine, _evaluate_window
from backend.app.backtesting.types import BacktestConfig, Draw


def _make_draws(n: int, start: str = "2015-01-01") -> list[Draw]:
    """Create *n* draws spaced one week apart."""
    base = datetime.fromisoformat(start)
    return [
        Draw(
            id=i,
            draw_date=base + timedelta(weeks=i),
            numbers=(1, 2, 3, 4, 5),
            super_number=10,
        )
        for i in range(n)
    ]


class _Static:
    """Minimal strategy for parity tests (dummy-v1)."""

    @property
    def strategy_id(self) -> str:
        return "dummy-v1"

    def predict(self, draw_context: Any) -> list[int]:
        return [1, 2, 3, 4, 5]


def _config(**overrides: Any) -> BacktestConfig:
    base: dict[str, Any] = {
        "min_train_draws": 10,
        "train_years": 1,
        "eval_count": 2,
        "step_count": 1,
        "seed": 42,
    }
    base.update(overrides)
    return BacktestConfig(**base)


class TestParallelParity:
    """GF-1 hard gate: serial and parallel outputs must be byte-identical."""

    def test_serial_parallel_byte_identical(self) -> None:
        draws = _make_draws(200)
        cfg = _config()
        strategy = _Static()

        serial = BacktestEngine().run(
            strategy=strategy, draws=draws, config=cfg, lottery_id=1, parallel=False
        )
        parallel = BacktestEngine().run(
            strategy=strategy, draws=draws, config=cfg, lottery_id=1, parallel=True
        )

        assert serial.fingerprint == parallel.fingerprint
        assert serial.aggregate_metrics == parallel.aggregate_metrics
        assert serial.window_history == parallel.window_history
        assert serial == parallel

    def test_window_index_order_preserved(self) -> None:
        draws = _make_draws(200)
        cfg = _config(eval_count=1)
        strategy = _Static()

        result = BacktestEngine().run(
            strategy=strategy, draws=draws, config=cfg, lottery_id=1, parallel=True
        )
        indexes = [w.window_index for w in result.window_history]
        assert indexes == list(range(len(indexes)))

    def test_single_window_serial_fallback(self) -> None:
        """Fewer than 2 windows falls back to the serial path."""
        draws = _make_draws(100)
        cfg = _config(min_train_draws=10, train_years=5, eval_count=1)
        strategy = _Static()

        serial = BacktestEngine().run(
            strategy=strategy, draws=draws, config=cfg, lottery_id=1, parallel=False
        )
        parallel = BacktestEngine().run(
            strategy=strategy, draws=draws, config=cfg, lottery_id=1, parallel=True
        )
        assert len(parallel.window_history) <= 1
        assert parallel == serial

    def test_evaluate_window_pickle_roundtrip(self) -> None:
        """Module-level worker is picklable (pool requirement)."""
        loaded = pickle.loads(pickle.dumps(_evaluate_window))
        assert loaded is _evaluate_window

    def test_no_db_in_worker_structural(self) -> None:
        """The worker body must not touch sessions or SQLAlchemy (PFM-04)."""
        src = inspect.getsource(_evaluate_window)
        assert "session" not in src.lower()
        assert "Session" not in src
        assert "sqlalchemy" not in src.lower()
        assert "core.db" not in src