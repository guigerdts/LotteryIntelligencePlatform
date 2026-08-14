/** Single combination row. */
export interface CombinationRow {
  position: number;
  numbers: number[];
  super_number: number | null;
  score: number | null;
}

/** Generation result from POST /gen/generate. */
export interface GenerationResult {
  snapshot_id: number;
  lottery_id: number;
  selection_id: number;
  version: string;
  status: string;
  fingerprint: string;
  seed: number;
  count: number;
  combinations: CombinationRow[];
}

/** Combination list from GET /gen/combinations. */
export interface CombinationList {
  snapshot_id: number;
  lottery_id: number;
  combinations: CombinationRow[];
}

/** Generator snapshot header. */
export interface GenSnapshot {
  snapshot_id: number;
  lottery_id: number;
  selection_id: number;
  version: string;
  status: string;
  fingerprint: string;
  created_at: string | null;
}

/** Generator snapshot list. */
export interface GenSnapshotList {
  lottery_id: number;
  snapshots: GenSnapshot[];
}

/** Snapshot status lifecycle. */
export type SnapshotStatus = "active" | "retired" | "failed";
