import type {
  GraphValuesResponse,
  ComputeSnapshot,
  GraphSnapshotList,
  GraphType,
} from "../types/graph";
import { apiClient } from "./api";

/** Trigger graph computation for a lottery. */
export async function computeGraph(
  lotteryCode: string,
  graphType: GraphType = "cooccurrence",
): Promise<ComputeSnapshot> {
  return apiClient<ComputeSnapshot>("/graph/compute", {
    method: "POST",
    body: JSON.stringify({ lottery_code: lotteryCode, graph_type: graphType }),
  });
}

/** List graph snapshots for a lottery. */
export async function getGraphSnapshots(
  lotteryCode: string,
  graphType?: GraphType,
): Promise<GraphSnapshotList> {
  const params = graphType ? `?graph_type=${graphType}` : "";
  return apiClient<GraphSnapshotList>(
    `/graph/${lotteryCode}/snapshots${params}`,
  );
}

/** Get graph values for a specific snapshot. */
export async function getGraphValues(
  lotteryCode: string,
  snapshotId: number,
): Promise<GraphValuesResponse> {
  return apiClient<GraphValuesResponse>(
    `/graph/${lotteryCode}/snapshots/${snapshotId}`,
  );
}
