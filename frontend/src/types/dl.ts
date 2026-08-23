/** Active DL snapshot metadata (GET /dl/models). Adds `window` vs MLSnapshot. */
export interface DLSnapshot {
  id: number;
  lottery_id: number;
  model_set: string;
  version: string;
  status: string;
  checksum: string;
  input_fingerprint: string;
  cut: number;
  window: number;
}

/** One persisted DL metric row (GET /dl/metrics). */
export interface DLMetric {
  model_id: string;
  number: number;
  metric_name: string;
  value: number;
  params_json: string;
}

/** Per-family DL training row inside the HTTP 200 train envelope. */
export interface DLTrainRow {
  family: "mlp" | "lstm";
  status: string;
  snapshot_id?: number | null;
  fingerprint?: string | null;
  metrics_checksum?: string | null;
  error?: string | null;
}

/** DL train response. */
export interface DLTrainResult {
  lottery_id: number;
  results: DLTrainRow[];
}
