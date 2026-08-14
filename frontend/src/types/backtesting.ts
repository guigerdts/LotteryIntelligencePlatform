/** Backtest run response. */
export interface BacktestRun {
  snapshot_id: number;
  lottery_id: number;
  strategy_id: string;
  fingerprint: string;
  version: string;
  status: string;
}

/** Backtest history entry. */
export interface BacktestHistoryEntry {
  snapshot_id: number;
  lottery_id: number;
  strategy_id: string;
  fingerprint: string;
  version: string;
  status: string;
  created_at: string;
}

/** Backtest metrics. */
export interface BacktestMetrics {
  hit_rate: number;
  average_matches: number;
  consistency_score: number;
  total_draws_evaluated: number;
}

/** Backtest window result. */
export interface BacktestWindow {
  window_index: number;
  train_range: [number, number];
  eval_range: [number, number];
  strategy_metrics: BacktestMetrics;
  uniform_metrics: BacktestMetrics | null;
  hypergeometric_metrics: BacktestMetrics | null;
}

/** Backtest result response. */
export interface BacktestResult {
  snapshot_id: number;
  lottery_id: number;
  strategy_id: string;
  fingerprint: string;
  version: string;
  status: string;
  aggregate_metrics: BacktestMetrics;
  window_history: BacktestWindow[];
}
