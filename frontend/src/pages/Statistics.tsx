import { useEffect, useState, type ReactNode } from "react";
import AverageChart from "../charts/AverageChart";
import FrequencyChart from "../charts/FrequencyChart";
import GapChart from "../charts/GapChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { generateStatistics, getAverages, getFrequencies, getGaps } from "../services/statistics";
import { useLotteryStore } from "../store/useLotteryStore";
import type { AverageList, FrequencyList, GapList } from "../types/statistics";

type StatTab = "frequencies" | "gaps" | "averages";
type StatList = FrequencyList | GapList | AverageList;

const NO_LOTTERY_MESSAGE = "Select a lottery to see its statistics.";
const NO_DATA_MESSAGE = "No statistics available for this lottery.";
const TABS: { id: StatTab; label: string }[] = [
  { id: "frequencies", label: "Frequencies" },
  { id: "gaps", label: "Gaps" },
  { id: "averages", label: "Averages" },
];

function SnapshotHeader({ list }: { list: StatList }) {
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
      <span>
        Draws <span className="font-medium text-gray-900">{list.draw_count}</span>
      </span>
      <span>
        Range{" "}
        <span className="font-medium text-gray-900">
          {list.draws_from}–{list.draws_to}
        </span>
      </span>
      <span>
        Snapshot <span className="font-medium text-gray-900">#{list.snapshot_id}</span>
      </span>
    </p>
  );
}

interface ChartPanelProps {
  list: StatList | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  empty: boolean;
  children: ReactNode;
}

function ChartPanel({ list, loading, error, onRetry, empty, children }: ChartPanelProps) {
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading) return <Skeleton variant="card" />;
  if (!list || empty) return <EmptyState message={NO_DATA_MESSAGE} />;
  return (
    <>
      <SnapshotHeader list={list} />
      {children}
    </>
  );
}

/**
 * Statistics page (Estadísticas). Tabbed frequency / gap / average chart views
 * for the globally selected lottery with a generate-snapshot action.
 */
export default function Statistics() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const [activeTab, setActiveTab] = useState<StatTab>("frequencies");
  const {
    data: freq,
    isLoading: freqLoading,
    error: freqError,
    execute: fetchFrequencies,
  } = useApi(getFrequencies);
  const {
    data: gaps,
    isLoading: gapsLoading,
    error: gapsError,
    execute: fetchGaps,
  } = useApi(getGaps);
  const {
    data: averages,
    isLoading: avgLoading,
    error: avgError,
    execute: fetchAverages,
  } = useApi(getAverages);
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

  const averageSeries = Object.entries(averages?.averages ?? {}).map(([seriesKey, row]) => ({
    series_key: seriesKey,
    ...row,
  }));

  const renderContent = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (activeTab === "frequencies") {
      return (
        <ChartPanel
          list={freq}
          loading={freqLoading}
          error={freqError}
          empty={!freq?.frequencies.length}
          onRetry={() => void fetchFrequencies(selectedLotteryCode)}
        >
          {freq && <FrequencyChart rows={freq.frequencies} />}
        </ChartPanel>
      );
    }
    if (activeTab === "gaps") {
      return (
        <ChartPanel
          list={gaps}
          loading={gapsLoading}
          error={gapsError}
          empty={!gaps?.gaps.length}
          onRetry={() => void fetchGaps(selectedLotteryCode)}
        >
          {gaps && <GapChart rows={gaps.gaps} />}
        </ChartPanel>
      );
    }
    return (
      <ChartPanel
        list={averages}
        loading={avgLoading}
        error={avgError}
        empty={averageSeries.length === 0}
        onRetry={() => void fetchAverages(selectedLotteryCode)}
      >
        {averages && <AverageChart series={averageSeries} />}
      </ChartPanel>
    );
  };

  const tabClass = (active: boolean) =>
    `rounded-md px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
      active
        ? "bg-blue-600 text-white"
        : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
    }`;

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Statistics</h2>
          <p className="text-sm text-gray-500">
            Frequencies, gaps and averages for the selected lottery.
          </p>
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
