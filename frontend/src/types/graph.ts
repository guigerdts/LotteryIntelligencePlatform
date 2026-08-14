/** Graph value row — metric_type + subject + value. */
export interface GraphValueRow {
  metric_type: string;
  subject: string;
  draw_number: number | null;
  value: number;
}

/** Graph values response. */
export interface GraphValuesResponse {
  rows: GraphValueRow[];
  count: number;
}

/** Compute snapshot header. */
export interface ComputeSnapshot {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  graph_type: string;
  graph_generator_version: string;
  draws_from: number;
  draws_to: number;
  draw_count: number;
  checksum: string;
  fingerprint: string;
}

/** Graph snapshot info for listing. */
export interface GraphSnapshotInfo {
  snapshot_id: number;
  lottery_code: string;
  version: string;
  graph_type: string;
  status: string;
  draw_count: number;
  created_at: string;
}

/** Graph snapshot list response. */
export interface GraphSnapshotList {
  snapshots: GraphSnapshotInfo[];
}

/** Graph type enum. */
export type GraphType = "cooccurrence" | "centrality" | "community" | "network";
