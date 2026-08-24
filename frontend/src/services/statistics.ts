import type { FrequencyList, GapList, AverageList, StatisticsSnapshot } from "../types/statistics";
import { apiClient } from "./api";

/** Trigger statistics generation for a lottery. */
export async function generateStatistics(
  lotteryCode: string,
  scope: "incremental" | "full" = "incremental"
): Promise<StatisticsSnapshot> {
  return apiClient<StatisticsSnapshot>("/statistics/generate", {
    method: "POST",
    body: JSON.stringify({ lottery_code: lotteryCode, scope }),
  });
}

/** Fetch frequency distribution for a lottery. */
export async function getFrequencies(lotteryCode: string, last?: number): Promise<FrequencyList> {
  const params = last !== undefined ? `?last=${last}` : "";
  return apiClient<FrequencyList>(`/statistics/${lotteryCode}/frequencies${params}`);
}

/** Fetch gap analysis for a lottery. */
export async function getGaps(lotteryCode: string, last?: number): Promise<GapList> {
  const params = last !== undefined ? `?last=${last}` : "";
  return apiClient<GapList>(`/statistics/${lotteryCode}/gaps${params}`);
}

/** Fetch averages for a lottery. */
export async function getAverages(lotteryCode: string, last?: number): Promise<AverageList> {
  const params = last !== undefined ? `?last=${last}` : "";
  return apiClient<AverageList>(`/statistics/${lotteryCode}/averages${params}`);
}
