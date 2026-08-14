import type { Lottery } from "../types/lottery";
import { apiClient } from "./api";

/** Fetch all lotteries (paginated). */
export async function getLotteries(
  page = 1,
  pageSize = 100,
): Promise<Lottery[]> {
  return apiClient<Lottery[]>(`/lotteries?page=${page}&page_size=${pageSize}`);
}
