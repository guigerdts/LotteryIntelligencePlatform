import type {
  GenerationResult,
  CombinationList,
  GenSnapshotList,
  SnapshotStatus,
} from "../types/gen";
import { apiClient } from "./api";

/** Generate combinations for a lottery. */
export async function generateCombinations(params: {
  lottery_id: number;
  count?: number;
  seed?: number;
  selection_id?: number;
}): Promise<GenerationResult> {
  return apiClient<GenerationResult>("/gen/generate", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

/** Get combinations for a snapshot. */
export async function getCombinations(
  lotteryId: number,
  snapshotId: number
): Promise<CombinationList> {
  return apiClient<CombinationList>(
    `/gen/combinations?lottery_id=${lotteryId}&snapshot_id=${snapshotId}`
  );
}

/** List generator snapshots for a lottery. */
export async function getSnapshots(lotteryId: number): Promise<GenSnapshotList> {
  return apiClient<GenSnapshotList>(`/gen/snapshots?lottery_id=${lotteryId}`);
}

/** Update snapshot status. */
export async function updateSnapshot(params: {
  lottery_id: number;
  snapshot_id: number;
  status: SnapshotStatus;
}): Promise<{ snapshot_id: number; status: string }> {
  return apiClient("/gen/snapshot", {
    method: "POST",
    body: JSON.stringify(params),
  });
}
