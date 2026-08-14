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

/** ML metrics entry. */
export interface MLMetrics {
  model_id: string;
  family: string;
  metrics: Record<string, number>;
}
