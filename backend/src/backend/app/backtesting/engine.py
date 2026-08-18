"""BacktestEngine orchestrator (BTE-02, BTE-07, BTE-10, BTE-15).

Orchestrates the full walk-forward backtest cycle: data floor validation,
deterministic window generation, strategy + benchmark evaluation, metric
computation, and result aggregation.  The engine never persists directly;
persistence is delegated to ``BtSnapshotStore``.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Any

from backend.app.backtesting.benchmark import (
    HypergeometricBenchmark,
    UniformRandomBenchmark,
)
from backend.app.backtesting.determinism import DeterminismContext
from backend.app.backtesting.fingerprint import compute_bt_fingerprint
from backend.app.backtesting.metrics import LotteryMetrics
from backend.app.backtesting.splitter import WalkForwardSplitter, Window
from backend.app.backtesting.strategy import StaticStrategy
from backend.app.backtesting.types import (
    BacktestConfig,
    BacktestResult,
    Draw,
    DrawContext,
    MetricSet,
    WindowResult,
)
from backend.app.services.errors import InsufficientDataError

_POOL_MAX_WORKERS = 2


def _evaluate_window(
    window: Window,
    strategy_id: str,
    config: BacktestConfig,
    lottery_id: int,
    number_pool: list[int],
    pick_count: int,
) -> tuple[int, MetricSet, MetricSet | None, MetricSet | None]:
    """Evaluate a single walk-forward window (T-S3-02, PFM-04).

    Pure worker: no DB access, plain-data payloads only.  Builds the
    draw contexts, a module-level ``StaticStrategy``, and per-window
    benchmarks seeded with ``random.Random(config.seed + window_index)``
    so every window is a deterministic function of its index — the same
    code path the serial loop uses, which keeps serial and parallel
    outputs byte-identical (GF-1).

    Returns:
        ``(window_index, strategy_metrics, uniform_metrics, hyper_metrics)``.
    """
    eval_draws = list(window.eval_draws)
    historical = tuple(window.train_draws + window.eval_draws)

    eval_contexts = [
        DrawContext(
            lottery_id=lottery_id,
            draw_date=d.draw_date,
            historical_draws=historical,
        )
        for d in eval_draws
    ]
    actuals = [list(d.numbers) for d in eval_draws]

    strategy = StaticStrategy(strategy_id)
    sub_seed = config.seed + window.index
    uniform = UniformRandomBenchmark(number_pool, pick_count, sub_seed)
    hyper = HypergeometricBenchmark(number_pool, pick_count, sub_seed)

    strategy_preds = [strategy.predict(ctx) for ctx in eval_contexts]
    uniform_preds = [uniform.predict(ctx) for ctx in eval_contexts]
    hyper_preds = [hyper.predict(ctx) for ctx in eval_contexts]

    strategy_metrics = LotteryMetrics.compute(strategy_preds, actuals)
    uniform_metrics = LotteryMetrics.compute(uniform_preds, actuals)
    hyper_metrics = LotteryMetrics.compute(hyper_preds, actuals)

    return window.index, strategy_metrics, uniform_metrics, hyper_metrics


class BacktestEngine:
    """Orchestrates walk-forward backtesting (BTE-10, BTE-15).

    The engine is a pure function of its inputs — no DB access, no side
    effects beyond the returned ``BacktestResult``.  Persistence is
    handled by the caller via ``BtSnapshotStore``.
    """

    def run(
        self,
        *,
        strategy: Any,
        draws: list[Draw],
        config: BacktestConfig,
        lottery_id: int,
        number_pool: list[int] | None = None,
        pick_count: int = 5,
        parallel: bool = False,
    ) -> BacktestResult:
        """Execute backtest in one deterministic pass.

        Parameters:
            strategy: Object satisfying ``StrategyProtocol`` (strategy_id + predict).
            draws: Chronologically sorted historical draws.
            config: Walk-forward configuration.
            lottery_id: Lottery identifier for scoping (BTE-14).
            number_pool: Pool of numbers for benchmarks (default 1..50).
            pick_count: Numbers to pick per draw (default 5).
            parallel: Use a bounded ``ProcessPoolExecutor`` when 2+ windows
                exist; serial path otherwise (T-S3-03, PFM-04).

        Returns:
            ``BacktestResult`` with aggregate and per-window metrics.

        Raises:
            InsufficientDataError: If draws < config.min_train_draws (BTE-07).
        """
        # 1. Data floor (BTE-07)
        if len(draws) < config.min_train_draws:
            raise InsufficientDataError(
                f"Need at least {config.min_train_draws} draws, got {len(draws)}"
            )

        # 2. Determinism context (BTE-05)
        DeterminismContext(config.seed)

        # 3. Compute fingerprint (BTE-06, BTE-18)
        data_hash = str(len(draws))  # simplified; real impl would hash dataset
        fingerprint = compute_bt_fingerprint(
            strategy_id=strategy.strategy_id,
            config=config,
            data_hash=data_hash,
            benchmark_type=config.benchmark_type,
        )

        # 4. Generate walk-forward windows (BTE-04)
        splitter = WalkForwardSplitter(config)
        windows = splitter.split(draws)

        # 5. Build benchmarks
        pool = number_pool or list(range(1, 51))

        # 6. Evaluate each window — serial loop or bounded process pool
        strategy_id = strategy.strategy_id
        if parallel and len(windows) >= 2:
            with ProcessPoolExecutor(max_workers=_POOL_MAX_WORKERS) as executor:
                evaluated = list(
                    executor.map(
                        _evaluate_window,
                        windows,
                        [strategy_id] * len(windows),
                        [config] * len(windows),
                        [lottery_id] * len(windows),
                        [pool] * len(windows),
                        [pick_count] * len(windows),
                    )
                )
        else:
            evaluated = [
                _evaluate_window(w, strategy_id, config, lottery_id, pool, pick_count)
                for w in windows
            ]

        window_results = [
            WindowResult(
                window_index=idx,
                train_range=(w.train_draws[0].id, w.train_draws[-1].id),
                eval_range=(w.eval_draws[0].id, w.eval_draws[-1].id),
                strategy_metrics=sm,
                uniform_metrics=um,
                hypergeometric_metrics=hm,
            )
            for w, (idx, sm, um, hm) in zip(windows, evaluated, strict=True)
        ]

        # 7. Aggregate metrics (BTE-15)
        if window_results:
            agg = LotteryMetrics.aggregate([wr.strategy_metrics for wr in window_results])
        else:
            agg = MetricSet(
                hit_rate=0,
                match_distribution={},
                average_matches=0,
                consistency_score=0,
                total_draws_evaluated=0,
            )

        return BacktestResult(
            fingerprint=fingerprint,
            lottery_id=lottery_id,
            strategy_id=strategy.strategy_id,
            status="active",
            aggregate_metrics=agg,
            window_history=tuple(window_results),
        )
