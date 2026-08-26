import type { ProbabilityList, ProbabilitySnapshot } from "../types/probability";
import { apiClient } from "./api";

/** Trigger probability generation for a lottery. */
export async function generateProbability(
  lotteryCode: string,
  scope: "incremental" | "full" = "incremental",
  signal?: AbortSignal
): Promise<ProbabilitySnapshot> {
  return apiClient<ProbabilitySnapshot>(
    "/probability/generate",
    {
      method: "POST",
      body: JSON.stringify({ lottery_code: lotteryCode, scope }),
    },
    signal
  );
}

/** Fetch probability rows for a lottery. */
export async function getProbabilities(
  lotteryCode: string,
  params?: { model?: string; subject?: string; last?: number }
): Promise<ProbabilityList> {
  const searchParams = new URLSearchParams();
  if (params?.model) searchParams.set("model", params.model);
  if (params?.subject) searchParams.set("subject", params.subject);
  if (params?.last !== undefined) searchParams.set("last", String(params.last));
  const qs = searchParams.toString();
  return apiClient<ProbabilityList>(
    `/probability/${lotteryCode}/probabilities${qs ? `?${qs}` : ""}`
  );
}
