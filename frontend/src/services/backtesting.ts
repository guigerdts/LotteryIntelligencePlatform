import type { BacktestRun, BacktestHistoryEntry, BacktestResult } from "../types/backtesting";
import { apiClient } from "./api";

/** Run a backtest. */
export async function runBacktest(params: {
  lottery_id: number;
  strategy_id: string;
  train_years?: number;
  eval_count?: number;
  step_count?: number;
  min_train_draws?: number;
  seed?: number;
}): Promise<BacktestRun> {
  return apiClient<BacktestRun>("/backtesting/run", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

/** Get backtest history for a lottery. */
export async function getBacktestHistory(lotteryId: number): Promise<BacktestHistoryEntry[]> {
  return apiClient<BacktestHistoryEntry[]>(`/backtesting/history?lottery_id=${lotteryId}`);
}

/** Get backtest results for a lottery. */
export async function getBacktestResults(
  lotteryId: number,
  snapshotId?: number
): Promise<BacktestResult> {
  const params = snapshotId ? `&snapshot_id=${snapshotId}` : "";
  return apiClient<BacktestResult>(`/backtesting/results?lottery_id=${lotteryId}${params}`);
}
