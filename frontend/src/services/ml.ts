import type { MLTrainResult, MLMetrics } from "../types/ml";
import { apiClient } from "./api";

/** Trigger ML training for a lottery. */
export async function trainModels(
  lotteryId: number,
  family?: string,
): Promise<MLTrainResult> {
  const params = family ? `&family=${family}` : "";
  return apiClient<MLTrainResult>(
    `/ml/train?lottery_id=${lotteryId}${params}`,
    { method: "POST" },
  );
}

/** Get active ML models for a lottery. */
export async function getModels(
  lotteryId: number,
): Promise<Record<string, unknown>> {
  return apiClient<Record<string, unknown>>(
    `/ml/models?lottery_id=${lotteryId}`,
  );
}

/** Get ML metrics for a lottery. */
export async function getMetrics(
  lotteryId: number,
  modelId?: string,
): Promise<MLMetrics[]> {
  const params = modelId ? `&model_id=${modelId}` : "";
  return apiClient<MLMetrics[]>(`/ml/metrics?lottery_id=${lotteryId}${params}`);
}
