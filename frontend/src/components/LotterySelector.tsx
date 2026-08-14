import { useEffect, useRef, type ChangeEvent } from "react";
import { useLotteryStore } from "../store/useLotteryStore";

/**
 * Global lottery selector for the header.
 * Loads the lottery list through the store (GET /lotteries) on first mount
 * and persists the selection via the store's persist middleware.
 * Loading / empty / error states are minimal inline placeholders here;
 * shared Skeleton / EmptyState / ErrorState components land in U3.
 */
export default function LotterySelector() {
  const lotteries = useLotteryStore((s) => s.lotteries);
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const isLoading = useLotteryStore((s) => s.isLoading);
  const error = useLotteryStore((s) => s.error);
  const loadLotteries = useLotteryStore((s) => s.loadLotteries);
  const setSelected = useLotteryStore((s) => s.setSelected);

  const hasRequestedLoad = useRef(false);

  useEffect(() => {
    if (lotteries.length === 0 && !hasRequestedLoad.current) {
      hasRequestedLoad.current = true;
      void loadLotteries();
    }
  }, [lotteries.length, loadLotteries]);

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const id = Number(event.target.value);
    const option = lotteries.find((lottery) => lottery.id === id);
    if (option) {
      setSelected(option.id, option.code);
    }
  };

  if (isLoading && lotteries.length === 0) {
    return (
      <div role="status" aria-live="polite" className="text-sm text-gray-500">
        Loading lotteries...
      </div>
    );
  }

  if (error && lotteries.length === 0) {
    return (
      <div role="alert" className="flex items-center gap-3 text-sm text-red-600">
        <span>Failed to load lotteries. {error}</span>
        <button
          type="button"
          onClick={() => void loadLotteries()}
          className="font-medium underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <label
        htmlFor="lottery-select"
        className="text-sm font-medium text-gray-600"
      >
        Lottery
      </label>
      <select
        id="lottery-select"
        value={selectedLotteryId ?? ""}
        onChange={handleChange}
        disabled={lotteries.length === 0}
        className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {lotteries.length === 0 ? (
          <option value="">No lotteries available</option>
        ) : (
          <>
            <option value="">Select a lottery</option>
            {lotteries.map((lottery) => (
              <option key={lottery.id} value={lottery.id}>
                {lottery.name} ({lottery.code})
              </option>
            ))}
          </>
        )}
      </select>
    </div>
  );
}