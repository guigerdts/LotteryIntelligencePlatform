import { useEffect, useMemo, useState } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { generateStatistics, getAverages, getFrequencies, getGaps } from "../services/statistics";
import { useLotteryStore } from "../store/useLotteryStore";
import type { AverageList, AverageRow, FrequencyList, FrequencyRow, GapList, GapRow } from "../types/statistics";

type StatTab = "frequencies" | "gaps" | "averages";
type StatList = FrequencyList | GapList | AverageList;

const NO_LOTTERY_MESSAGE = "Select a lottery to see its statistics.";
const NO_DATA_MESSAGE = "No statistics available for this lottery.";
const TABS: { id: StatTab; label: string }[] = [
  { id: "frequencies", label: "Frequencies" },
  { id: "gaps", label: "Gaps" },
  { id: "averages", label: "Averages" },
];

const gapColumns: DataColumn<GapRow>[] = [
  { key: "number", label: "Number", sortable: true },
  { key: "count", label: "Count", sortable: true },
  { key: "min_gap", label: "Min gap", render: (r) => r.min_gap ?? "—" },
  { key: "max_gap", label: "Max gap", render: (r) => r.max_gap ?? "—" },
  { key: "avg_gap", label: "Avg gap", render: (r) => r.avg_gap?.toFixed(1) ?? "—" },
];

const averageColumns: DataColumn<AverageRow & { series: string }>[] = [
  { key: "series", label: "Series", sortable: true },
  { key: "mean", label: "Mean", render: (r) => r.mean?.toFixed(2) ?? "—" },
  { key: "non_null_count", label: "Non-null count", sortable: true },
];

const frequencyColumns: DataColumn<FrequencyRow & { pct: string }>[] = [
  { key: "number", label: "Number", sortable: true },
  { key: "count", label: "Count", sortable: true },
  { key: "pct", label: "%", render: (r) => r.pct },
];

function SnapshotHeader({ list }: { list: StatList | null }) {
  if (!list) return null;
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
      <span>Draws <span className="font-medium text-gray-900">{list.draw_count}</span></span>
      <span>Range <span className="font-medium text-gray-900">{list.draws_from}–{list.draws_to}</span></span>
      <span>Snapshot <span className="font-medium text-gray-900">#{list.snapshot_id}</span></span>
    </p>
  );
}

interface TablePanelProps<T> {
  list: StatList | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
}

function TablePanel<T>({ list, loading, error, onRetry, columns, rows, rowKey, caption }: TablePanelProps<T>) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton variant="card" />;
  if (rows.length === 0) return <EmptyState message={NO_DATA_MESSAGE} />;
  return (
    <>
      <SnapshotHeader list={list} />
      <DataTable columns={columns} rows={rows} rowKey={rowKey} caption={caption} loading={loading} loadingRows={5} />
    </>
  );
}

/**
 * Statistics page (Estadísticas). Tabbed frequency / gap / average tables for
 * the globally selected lottery with a generate-snapshot action. Chart views
 * are covered by Tier 2/3; this slice renders tabular representations.
 */
export default function Statistics() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const [activeTab, setActiveTab] = useState<StatTab>("frequencies");
  const { data: freq, isLoading: freqLoading, error: freqError, execute: fetchFrequencies } = useApi(getFrequencies);
  const { data: gaps, isLoading: gapsLoading, error: gapsError, execute: fetchGaps } = useApi(getGaps);
  const { data: averages, isLoading: avgLoading, error: avgError, execute: fetchAverages } = useApi(getAverages);
  const { isLoading: generating, execute: generate } = useApi(generateStatistics);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    void fetchFrequencies(selectedLotteryCode);
    void fetchGaps(selectedLotteryCode);
    void fetchAverages(selectedLotteryCode);
  }, [selectedLotteryCode, fetchFrequencies, fetchGaps, fetchAverages]);

  const handleGenerate = async () => {
    if (!selectedLotteryCode) return;
    await generate(selectedLotteryCode);
    void fetchFrequencies(selectedLotteryCode);
    void fetchGaps(selectedLotteryCode);
    void fetchAverages(selectedLotteryCode);
  };

  const freqRows = useMemo(() => {
    const rows = freq?.frequencies ?? [];
    const total = rows.reduce((s, r) => s + r.count, 0);
    return rows.map((r) => ({ ...r, pct: total > 0 ? `${((r.count / total) * 100).toFixed(1)}%` : "0%" }));
  }, [freq]);

  const renderContent = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (activeTab === "frequencies") {
      return (
        <TablePanel
          list={freq}
          loading={freqLoading}
          error={freqError}
          onRetry={() => void fetchFrequencies(selectedLotteryCode)}
          columns={frequencyColumns}
          rows={freqRows}
          rowKey={(row) => String(row.number)}
          caption="Frequency distribution"
        />
      );
    }
    if (activeTab === "gaps") {
      return (
        <TablePanel
          list={gaps}
          loading={gapsLoading}
          error={gapsError}
          onRetry={() => void fetchGaps(selectedLotteryCode)}
          columns={gapColumns}
          rows={gaps?.gaps ?? []}
          rowKey={(row) => String(row.number)}
          caption="Gap analysis"
        />
      );
    }
    return (
      <TablePanel
        list={averages}
        loading={avgLoading}
        error={avgError}
        onRetry={() => void fetchAverages(selectedLotteryCode)}
        columns={averageColumns}
        rows={Object.entries(averages?.averages ?? {}).map(([series, row]) => ({ series, ...row }))}
        rowKey={(row) => row.series}
        caption="Average series"
      />
    );
  };

  const tabClass = (active: boolean) =>
    `rounded-md px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
      active ? "bg-blue-600 text-white" : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
    }`;

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Statistics</h2>
          <p className="text-sm text-gray-500">Frequencies, gaps and averages for the selected lottery.</p>
        </div>
        <button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={!selectedLotteryCode || generating}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {generating ? "Generating…" : "Generate Snapshot"}
        </button>
      </div>
      <div role="tablist" aria-label="Statistics views" className="flex gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`stat-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={tabClass(activeTab === tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        aria-labelledby={`stat-tab-${activeTab}`}
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </div>
    </div>
  );
}
