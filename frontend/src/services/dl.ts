import type { DLTrainResult, DLMetric, DLSnapshot } from "../types/dl";
import { apiClient, NotFoundError } from "./api";

/** Trigger DL training for a lottery (v1 defaults model_set/window server-side). */
export async function trainDlModels(lotteryId: number): Promise<DLTrainResult> {
  return apiClient<DLTrainResult>(`/dl/train?lottery_id=${lotteryId}`, {
    method: "POST",
  });
}

/**
 * Get the active DL snapshot for a lottery.
 * A 404 SNAPSHOT_NOT_FOUND resolves to `null` so the page can render its
 * empty-state Train CTA; any other failure rethrows (D1).
 */
export async function getDlModels(lotteryId: number): Promise<DLSnapshot | null> {
  try {
    return await apiClient<DLSnapshot>(`/dl/models?lottery_id=${lotteryId}`);
  } catch (error) {
    if (error instanceof NotFoundError && error.code === "SNAPSHOT_NOT_FOUND") {
      return null;
    }
    throw error;
  }
}

/** Get DL metrics for a lottery, optionally filtered by model family. */
export async function getDlMetrics(lotteryId: number, modelId?: string): Promise<DLMetric[]> {
  const params = modelId ? `&model_id=${modelId}` : "";
  return apiClient<DLMetric[]>(`/dl/metrics?lottery_id=${lotteryId}${params}`);
}
