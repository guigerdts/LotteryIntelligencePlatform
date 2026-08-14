/** Single frequency row: number + count. */
export interface FrequencyRow {
  number: number;
  count: number;
}

/** Frequencies response with snapshot header. */
export interface FrequencyList {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  frequencies: FrequencyRow[];
}

/** Single gap row per number. */
export interface GapRow {
  number: number;
  count: number;
  min_gap: number | null;
  max_gap: number | null;
  avg_gap: number | null;
}

/** Gaps response with snapshot header. */
export interface GapList {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  gaps: GapRow[];
}

/** Single average row per series. */
export interface AverageRow {
  mean: number | null;
  non_null_count: number;
}

/** Averages response with snapshot header. */
export interface AverageList {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  averages: Record<string, AverageRow>;
}

/** Statistics generate snapshot header. */
export interface StatisticsSnapshot {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  metric_set: string;
  generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  incremental: boolean;
}
