import type { AssistantResponse, SummarizeRequest } from "../types/assistant";
import { apiClient } from "./api";

export type ReportScope =
  | "frequency"
  | "gap"
  | "average"
  | "probability"
  | "experiment";

/** Request a Spanish explanation of a lottery's results (optional subject/context). */
export async function explainAssistant(
  lotteryCode: string,
  subject?: string,
  context?: string,
): Promise<AssistantResponse> {
  const searchParams = new URLSearchParams({ lottery_code: lotteryCode });
  if (subject) searchParams.set("subject", subject);
  if (context) searchParams.set("context", context);
  return apiClient<AssistantResponse>(
    `/assistant/explain?${searchParams.toString()}`,
  );
}

/** Request a Spanish interpretation of the data behind the charts. */
export async function interpretAssistant(
  lotteryCode: string,
): Promise<AssistantResponse> {
  const searchParams = new URLSearchParams({ lottery_code: lotteryCode });
  return apiClient<AssistantResponse>(
    `/assistant/interpret?${searchParams.toString()}`,
  );
}

/** Request a scoped Spanish plain-text report for a lottery. */
export async function reportAssistant(
  lotteryCode: string,
  scope?: ReportScope,
): Promise<AssistantResponse> {
  const searchParams = new URLSearchParams({ lottery_code: lotteryCode });
  if (scope) searchParams.set("scope", scope);
  return apiClient<AssistantResponse>(
    `/assistant/report?${searchParams.toString()}`,
  );
}

/** Summarize an experiment comparison in Spanish. */
export async function summarizeAssistant(
  req: SummarizeRequest,
): Promise<AssistantResponse> {
  return apiClient<AssistantResponse>("/assistant/summarize", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/** Route a free-text question to the matching generator (unknown -> capabilities). */
export async function assist(
  question: string,
  lotteryCode: string,
): Promise<AssistantResponse> {
  return apiClient<AssistantResponse>("/assistant/assist", {
    method: "POST",
    body: JSON.stringify({ question, lottery_code: lotteryCode }),
  });
}