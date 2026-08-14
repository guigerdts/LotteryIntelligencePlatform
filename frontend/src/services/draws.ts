import type { Draw } from "../types/draw";
import { apiClient } from "./api";

/** Fetch draws for a lottery, ordered descending. */
export async function getDraws(
  lotteryCode: string,
  page = 1,
  pageSize = 50,
): Promise<Draw[]> {
  return apiClient<Draw[]>(
    `/draws?lottery=${lotteryCode}&order=desc&page=${page}&page_size=${pageSize}`,
  );
}

/** Fetch a single draw by ID. */
export async function getDraw(id: number): Promise<Draw> {
  return apiClient<Draw>(`/draws/${id}`);
}
