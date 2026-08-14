/** Experiment read model. */
export interface Experiment {
  experiment_id: number;
  lottery_id: number;
  name: string;
  description: string | null;
  fingerprint: string;
  version: string;
  status: string;
  config_json: string | null;
  created_at: string;
}

/** Run associated with an experiment. */
export interface ExperimentRun {
  run_id: number;
  experiment_id: number;
  run_label: string;
  engine_type: string;
  engine_snapshot_id: number;
  engine_fingerprint: string;
  notes: string | null;
}

/** Comparison run entry. */
export interface ComparisonRunEntry {
  run_id: number;
  run_label: string;
  engine_type: string;
  engine_snapshot_id: number;
  metrics: Record<string, number>;
}

/** Comparison response. */
export interface ComparisonResponse {
  comparison_id: number;
  experiment_id: number;
  runs: ComparisonRunEntry[];
  metric_names: string[];
  created_at: string;
}
