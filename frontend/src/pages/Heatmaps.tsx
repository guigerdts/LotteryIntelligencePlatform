import { useEffect, useState } from "react";
import HeatmapChart from "../charts/HeatmapChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { computeGraph, getGraphSnapshots, getGraphValues } from "../services/graph";
import { useLotteryStore } from "../store/useLotteryStore";
import type { GraphSnapshotInfo } from "../types/graph";

const NO_LOTTERY_MESSAGE = "Select a lottery to see co-occurrence heatmaps.";
const NO_DATA_MESSAGE = "No co-occurrence snapshot for this lottery. Click Compute to generate one.";
const NO_PAIRS_MESSAGE = "No co-occurrence pairs in this snapshot.";
const BUTTON_CLASS = "rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

function snapshotClass(selected: boolean): string {
  return `flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border px-3 py-2 text-left text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
    selected ? "border-blue-600 bg-blue-50 text-gray-900" : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
  }`;
}

/** Heatmaps page: compute + select co-occurrence snapshots → SVG heatmap grid. */
export default function Heatmaps() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const { data: snapshotList, isLoading: loadingList, error: listError, execute: fetchSnapshots } = useApi(getGraphSnapshots);
  const { data: values, isLoading: loadingValues, error: valuesError, execute: fetchValues } = useApi(getGraphValues);
  const { isLoading: computing, error: computeError, execute: compute } = useApi(computeGraph);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    setSelectedId(null);
    void fetchSnapshots(selectedLotteryCode, "cooccurrence");
  }, [selectedLotteryCode, fetchSnapshots]);

  useEffect(() => {
    if (selectedId !== null || !snapshotList) return;
    const latest = snapshotList.snapshots[0];
    if (latest) setSelectedId(latest.snapshot_id);
  }, [snapshotList, selectedId]);

  useEffect(() => {
    if (!selectedLotteryCode || selectedId === null) return;
    void fetchValues(selectedLotteryCode, selectedId);
  }, [selectedLotteryCode, selectedId, fetchValues]);

  const snapshots = snapshotList?.snapshots ?? [];
  const selected = snapshots.find((item) => item.snapshot_id === selectedId) ?? null;
  const cooccurrenceRows = values?.rows.filter((row) => row.metric_type === "cooccurrence") ?? [];
  const heatmapRows = cooccurrenceRows.map((row) => ({ subject: row.subject, value: row.value }));

  const handleCompute = async () => {
    if (!selectedLotteryCode || computing) return;
    await compute(selectedLotteryCode, "cooccurrence");
    setSelectedId(null);
    void fetchSnapshots(selectedLotteryCode, "cooccurrence");
  };

  const renderVisualization = (code: string, item: GraphSnapshotInfo) => {
    if (valuesError) return <ErrorState message={valuesError} onRetry={() => void fetchValues(code, item.snapshot_id)} />;
    if (loadingValues) return <Skeleton variant="card" />;
    if (cooccurrenceRows.length === 0) return <EmptyState message={NO_PAIRS_MESSAGE} />;
    return (
      <div className="space-y-4">
        <HeatmapChart rows={heatmapRows} />
        <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
          <span>Draws <span className="font-medium text-gray-900">{item.draw_count}</span></span>
          <span>Pairs <span className="font-medium text-gray-900">{cooccurrenceRows.length}</span></span>
        </p>
      </div>
    );
  };

  const renderContent = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (computeError) return <ErrorState message={computeError} onRetry={() => void handleCompute()} />;
    if (listError) return <ErrorState message={listError} onRetry={() => void fetchSnapshots(selectedLotteryCode, "cooccurrence")} />;
    if (loadingList) return <Skeleton variant="card" />;
    if (snapshots.length === 0) {
      return (
        <EmptyState
          message={NO_DATA_MESSAGE}
          action={<button type="button" onClick={() => void handleCompute()} disabled={computing} className={BUTTON_CLASS}>{computing ? "Computing…" : "Compute"}</button>}
        />
      );
    }
    return (
      <div className="space-y-5">
        <ul className="flex flex-col gap-2 sm:max-w-md" aria-label="Co-occurrence snapshots">
          {snapshots.map((item) => (
            <li key={item.snapshot_id}>
              <button type="button" aria-pressed={selectedId === item.snapshot_id} onClick={() => setSelectedId(item.snapshot_id)} className={snapshotClass(selectedId === item.snapshot_id)}>
                <span className="font-medium">#{item.snapshot_id}</span>
                <span>v{item.version} · {item.draw_count} draws · {item.status} · {new Date(item.created_at).toLocaleDateString()}</span>
              </button>
            </li>
          ))}
        </ul>
        {selected ? renderVisualization(selectedLotteryCode, selected) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Heatmaps</h2>
          <p className="text-sm text-gray-500">Co-occurrence strength between number pairs for the selected lottery.</p>
        </div>
        <button type="button" onClick={() => void handleCompute()} disabled={!selectedLotteryCode || computing} aria-busy={computing} className={BUTTON_CLASS}>
          {computing ? "Computing…" : "Compute"}
        </button>
      </div>
      <section aria-label="Co-occurrence heatmaps" className="rounded-md border border-gray-200 bg-white p-4">
        {renderContent()}
      </section>
    </div>
  );
}