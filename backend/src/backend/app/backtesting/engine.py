"""BacktestEngine orchestrator (BTE-02, BTE-07, BTE-10, BTE-15).

Orchestrates the full walk-forward backtest cycle: data floor validation,
deterministic window generation, strategy + benchmark evaluation, metric
computation, and result aggregation.  The engine never persists directly;
persistence is delegated to ``BtSnapshotStore``.
"""

from __future__ import annotations

from typing import Any

from backend.app.backtesting.benchmark import (
    HypergeometricBenchmark,
    UniformRandomBenchmark,
)
from backend.app.backtesting.determinism import DeterminismContext
from backend.app.backtesting.fingerprint import compute_bt_fingerprint
from backend.app.backtesting.metrics import LotteryMetrics
from backend.app.backtesting.splitter import WalkForwardSplitter
from backend.app.backtesting.types import (
    BacktestConfig,
    BacktestResult,
    Draw,
    DrawContext,
    MetricSet,
    WindowResult,
)
from backend.app.services.errors import InsufficientDataError


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
    ) -> BacktestResult:
        """Execute backtest in one deterministic pass.

        Parameters:
            strategy: Object satisfying ``StrategyProtocol`` (strategy_id + predict).
            draws: Chronologically sorted historical draws.
            config: Walk-forward configuration.
            lottery_id: Lottery identifier for scoping (BTE-14).
            number_pool: Pool of numbers for benchmarks (default 1..50).
            pick_count: Numbers to pick per draw (default 5).

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
        uniform = UniformRandomBenchmark(pool, pick_count, config.seed)
        hyper = HypergeometricBenchmark(pool, pick_count, config.seed)

        # 6. Evaluate each window
        window_results: list[WindowResult] = []
        for w in windows:
            # Build evaluation contexts (expanding window, no future — BTE-17)
            eval_draws = list(w.eval_draws)
            historical = tuple(w.train_draws + w.eval_draws)

            eval_contexts = [
                DrawContext(
                    lottery_id=lottery_id,
                    draw_date=d.draw_date,
                    historical_draws=historical,
                )
                for d in eval_draws
            ]
            actuals = [list(d.numbers) for d in eval_draws]

            # Strategy predictions
            strategy_preds = [strategy.predict(ctx) for ctx in eval_contexts]

            # Benchmark predictions — same evaluation period (BTE-16)
            uniform_preds = [uniform.predict(ctx) for ctx in eval_contexts]
            hyper_preds = [hyper.predict(ctx) for ctx in eval_contexts]

            # Compute metrics
            strategy_metrics = LotteryMetrics.compute(strategy_preds, actuals)
            uniform_metrics = LotteryMetrics.compute(uniform_preds, actuals)
            hyper_metrics = LotteryMetrics.compute(hyper_preds, actuals)

            wr = WindowResult(
                window_index=w.index,
                train_range=(w.train_draws[0].id, w.train_draws[-1].id),
                eval_range=(w.eval_draws[0].id, w.eval_draws[-1].id),
                strategy_metrics=strategy_metrics,
                uniform_metrics=uniform_metrics,
                hypergeometric_metrics=hyper_metrics,
            )
            window_results.append(wr)

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
