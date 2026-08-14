import type { Experiment, ComparisonResponse } from "../types/experiment";
import { apiClient } from "./api";

/** List experiments for a lottery. */
export async function listExperiments(
  lotteryId: number,
  status?: string,
): Promise<Experiment[]> {
  const params = status ? `&status=${status}` : "";
  return apiClient<Experiment[]>(
    `/experiment/?lottery_id=${lotteryId}${params}`,
  );
}

/** Create a new experiment. */
export async function createExperiment(
  lotteryId: number,
  name: string,
  description?: string,
): Promise<Experiment> {
  return apiClient<Experiment>("/experiment/create", {
    method: "POST",
    body: JSON.stringify({ lottery_id: lotteryId, name, description }),
  });
}

/** Get experiment by ID. */
export async function getExperiment(id: number): Promise<Experiment> {
  return apiClient<Experiment>(`/experiment/${id}`);
}

/** Run an experiment (associate engine snapshot). */
export async function runExperiment(
  experimentId: number,
  runLabel: string,
  engineType: string,
  engineSnapshotId: number,
): Promise<{ run_id: number; experiment_id: number; run_label: string }> {
  return apiClient(`/experiment/${experimentId}/run`, {
    method: "POST",
    body: JSON.stringify({
      run_label: runLabel,
      engine_type: engineType,
      engine_snapshot_id: engineSnapshotId,
    }),
  });
}

/** Compare runs within an experiment. */
export async function compareRuns(
  experimentId: number,
  runIds: number[],
): Promise<ComparisonResponse> {
  return apiClient<ComparisonResponse>(`/experiment/${experimentId}/compare`, {
    method: "POST",
    body: JSON.stringify({ run_ids: runIds }),
  });
}
