import type { PipelineRunParams, PipelineRunResult } from "../types/pipeline";
import { apiClient } from "./api";

/**
 * Run the end-to-end numbers orchestrator (POST /pipeline/numbers). The sync
 * call may take minutes; the response carries the ordered per-stage report and
 * the generation echo (null when a stage failed).
 */
export async function runNumbersPipeline(params: PipelineRunParams): Promise<PipelineRunResult> {
  return apiClient<PipelineRunResult>("/pipeline/numbers", {
    method: "POST",
    body: JSON.stringify(params),
  });
}
