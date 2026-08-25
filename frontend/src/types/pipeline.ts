import type { GenerationResult } from "./gen";

/** Names of the three canonical pipeline stages, in execution order. */
export type PipelineStageName = "stats" | "features" | "gen";

/** Status of one stage entry in the per-stage report. */
export type PipelineStageStatus = "skipped" | "completed" | "failed";

/** One ordered stage entry of the POST /pipeline/numbers report (R2). */
export interface PipelineStageResult {
  name: PipelineStageName;
  status: PipelineStageStatus;
  snapshot_id: number | null;
  fingerprint: string | null;
  error_code: string | null;
  detail: string;
}

/**
 * Response data of POST /pipeline/numbers: the ordered three-stage report plus
 * the generation echo, which is null when any stage failed (S2 contract).
 */
export interface PipelineRunResult {
  stages: PipelineStageResult[];
  result: GenerationResult | null;
}

/** Payload for POST /pipeline/numbers. */
export interface PipelineRunParams {
  lottery_id: number;
  count?: number;
  seed?: number;
}
