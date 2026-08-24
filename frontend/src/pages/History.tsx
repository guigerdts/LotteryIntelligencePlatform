import { useEffect, useState } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import { useApi } from "../hooks/useApi";
import { getDraws } from "../services/draws";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Draw } from "../types/draw";

const PAGE_SIZE = 50;
const NO_LOTTERY_MESSAGE = "Select a lottery to see its draw history.";
const NO_DATA_MESSAGE = "No draws available for this lottery.";

const drawColumns: DataColumn<Draw>[] = [
  { key: "draw_number", label: "Draw", sortable: true },
  { key: "draw_date", label: "Date", sortable: true },
  {
    key: "numbers",
    label: "Numbers",
    render: (row) => row.numbers.map((n) => n.number).join(" - "),
  },
  {
    key: "super_number",
    label: "Super",
    render: (row) => row.super_number ?? "—",
  },
];

function PageNav({
  page,
  hasPrevious,
  hasNext,
  onPage,
}: {
  page: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPage: (page: number) => void;
}) {
  const navClass =
    "rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";
  return (
    <nav aria-label="Draw history pages" className="mt-4 flex items-center justify-between">
      <button
        type="button"
        onClick={() => onPage(page - 1)}
        disabled={!hasPrevious}
        className={navClass}
      >
        Previous
      </button>
      <span aria-live="polite" className="text-sm text-gray-500">
        Page {page}
      </span>
      <button
        type="button"
        onClick={() => onPage(page + 1)}
        disabled={!hasNext}
        className={navClass}
      >
        Next
      </button>
    </nav>
  );
}

/**
 * Draw history page (Historial). Shows a paginated table of draws for the
 * globally selected lottery using the page query param, with loading, empty,
 * error+retry and no-selection states.
 */
export default function History() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const [page, setPage] = useState(1);
  const { data, isLoading, error, execute } = useApi(getDraws);

  useEffect(() => {
    setPage(1);
  }, [selectedLotteryCode]);

  useEffect(() => {
    if (selectedLotteryCode) {
      void execute(selectedLotteryCode, page, PAGE_SIZE);
    }
  }, [selectedLotteryCode, page, execute]);

  const rows = data ?? [];
  const hasPrevious = page > 1;
  const hasNext = rows.length === PAGE_SIZE;

  const renderContent = () => {
    if (!selectedLotteryCode) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return (
        <ErrorState
          message={error}
          onRetry={() => void execute(selectedLotteryCode, page, PAGE_SIZE)}
        />
      );
    }
    if (rows.length === 0 && !isLoading) {
      return <EmptyState message={NO_DATA_MESSAGE} />;
    }
    return (
      <>
        <DataTable
          columns={drawColumns}
          rows={rows}
          rowKey={(row) => String(row.id)}
          caption="Draw history"
          loading={isLoading}
          loadingRows={PAGE_SIZE}
        />
        {!isLoading ? (
          <PageNav page={page} hasPrevious={hasPrevious} hasNext={hasNext} onPage={setPage} />
        ) : null}
      </>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">History</h2>
        <p className="text-sm text-gray-500">Paginated draw history for the selected lottery.</p>
      </div>
      {renderContent()}
    </div>
  );
}
