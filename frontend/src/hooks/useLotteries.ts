import { useEffect } from "react";
import { useLotteryStore, type LotteryState } from "../store/useLotteryStore";

/**
 * Hook that loads lotteries on mount and exposes the store.
 * Components can call useLotteries() to access the lottery list
 * and selected lottery without manually triggering the load.
 */
export function useLotteries() {
  const loadLotteries = useLotteryStore((s: LotteryState) => s.loadLotteries);
  const lotteries = useLotteryStore((s: LotteryState) => s.lotteries);
  const selectedLotteryId = useLotteryStore((s: LotteryState) => s.selectedLotteryId);
  const selectedLotteryCode = useLotteryStore((s: LotteryState) => s.selectedLotteryCode);
  const isLoading = useLotteryStore((s: LotteryState) => s.isLoading);
  const error = useLotteryStore((s: LotteryState) => s.error);
  const setSelected = useLotteryStore((s: LotteryState) => s.setSelected);

  useEffect(() => {
    if (lotteries.length === 0) {
      loadLotteries();
    }
  }, [lotteries.length, loadLotteries]);

  return {
    lotteries,
    selectedLotteryId,
    selectedLotteryCode,
    isLoading,
    error,
    setSelected,
  };
}
