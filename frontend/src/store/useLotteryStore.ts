import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LotteryOption } from "../types/lottery";
import { getLotteries } from "../services/lotteries";

export interface LotteryState {
  /** All available lotteries. */
  lotteries: LotteryOption[];
  /** Currently selected lottery ID (for /ml, /backtesting, /experiment, /gen). */
  selectedLotteryId: number | null;
  /** Currently selected lottery code (for /statistics, /probability, /graph, /draws). */
  selectedLotteryCode: string | null;
  /** Loading state for lottery list fetch. */
  isLoading: boolean;
  /** Error message from last fetch. */
  error: string | null;

  /** Fetch lotteries from API and populate the list. */
  loadLotteries: () => Promise<void>;
  /** Set the selected lottery atomically (id + code). */
  setSelected: (id: number | null, code: string | null) => void;
}

export const useLotteryStore = create<LotteryState>()(
  persist(
    (set) => ({
      lotteries: [],
      selectedLotteryId: null,
      selectedLotteryCode: null,
      isLoading: false,
      error: null,

      loadLotteries: async () => {
        set({ isLoading: true, error: null });
        try {
          const data = await getLotteries();
          const options: LotteryOption[] = data.map((l) => ({
            id: l.id,
            code: l.code,
            name: l.name,
            country: l.country,
          }));
          set({ lotteries: options, isLoading: false });
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : "Unknown error",
            isLoading: false,
          });
        }
      },

      setSelected: (id, code) => {
        set({ selectedLotteryId: id, selectedLotteryCode: code });
      },
    }),
    {
      name: "lip:selectedLottery",
      partialize: (state) => ({
        selectedLotteryId: state.selectedLotteryId,
        selectedLotteryCode: state.selectedLotteryCode,
      }),
    },
  ),
);
