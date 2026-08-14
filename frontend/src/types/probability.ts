/** Single probability row. */
export interface ProbRow {
  model_id: string;
  model_version: string;
  subject: string;
  draw_number: number | null;
  value: string;
}

/** Probabilities response with snapshot header. */
export interface ProbabilityList {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  prob_generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  probabilities: ProbRow[];
}

/** Probability generate snapshot header. */
export interface ProbabilitySnapshot {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  model_set: string;
  prob_generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  incremental: boolean;
}
