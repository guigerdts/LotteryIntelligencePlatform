/** Assistant text-generation response (envelope `data` shape). */
export interface AssistantResponse {
  text: string;
  engine_version: string;
  fingerprint: string;
}

/** Summarize request body: an experiment and optional runs to compare. */
export interface SummarizeRequest {
  experiment_id: number;
  run_ids?: number[];
}

/** Assist request body: free-text question bound to a lottery. */
export interface AssistRequest {
  question: string;
  lottery_code: string;
}
