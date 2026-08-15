/** ML model metadata. */
export interface MLModel {
  family: string;
  status: string;
  snapshot_id: number;
  fingerprint: string;
  metrics_checksum: string;
  error: string | null;
}

/** ML train response. */
export interface MLTrainResult {
  lottery_id: number;
  results: MLModel[];
}

/** Active ML snapshot metadata (GET /ml/models). */
export interface MLSnapshot {
  id: number;
  lottery_id: number;
  model_set: string;
  version: string;
  status: string;
  checksum: string;
  input_fingerprint: string;
  cut: number;
}

/** One persisted ML metric row (GET /ml/metrics). */
export interface MLMetrics {
  model_id: string;
  number: number;
  metric_name: string;
  value: number;
  params_json: string;
}
