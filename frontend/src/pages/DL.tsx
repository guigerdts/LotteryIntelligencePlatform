import { useEffect, useState } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getDlMetrics, getDlModels, trainDlModels } from "../services/dl";
import { useLotteryStore } from "../store/useLotteryStore";
import type { DLMetric, DLSnapshot, DLTrainResult } from "../types/dl";

const NO_LOTTERY_MESSAGE = "Select a lottery to see deep learning models.";
const NO_MODELS_MESSAGE =
  "No models trained yet for this lottery. Click Train to generate them.";
const NO_METRICS_MESSAGE = "No metrics available for this lottery.";
const BUTTON_CLASS =
  "rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

const metricColumns: DataColumn<DLMetric>[] = [
  { key: "model_id", label: "Model", sortable: true },
  { key: "number", label: "Number", sortable: true },
  { key: "metric_name", label: "Metric", sortable: true },
  { key: "value", label: "Value", sortable: true, sortValue: (row) => row.value },
];

/** Presentation order of metric families: mlp rows group before lstm rows (R2). */
const FAMILY_ORDER: Record<string, number> = { mlp: 0, lstm: 1 };

function SnapshotSummary({ snapshot }: { snapshot: DLSnapshot }) {
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
      <span>
        Snapshot <span className="font-medium text-gray-900">#{snapshot.id}</span>
      </span>
      <span>
        Model set{" "}
        <span className="font-medium text-gray-900">{snapshot.model_set}</span>
      </span>
      <span>
        Version <span className="font-medium text-gray-900">{snapshot.version}</span>
      </span>
      <span>
        Status <span className="font-medium text-gray-900">{snapshot.status}</span>
      </span>
      <span>
        Checksum{" "}
        <span className="font-mono text-xs text-gray-900">{snapshot.checksum}</span>
      </span>
      <span>
        Input fingerprint{" "}
        <span className="font-mono text-xs text-gray-900">
          {snapshot.input_fingerprint}
        </span>
      </span>
      <span>
        Cut <span className="font-medium text-gray-900">{snapshot.cut}</span>
      </span>
      <span>
        Window <span className="font-medium text-gray-900">{snapshot.window}</span>
      </span>
    </p>
  );
}

/**
 * Deep Learning page. Shows the active DL snapshot for the global lottery, its
 * persisted per-family (mlp/lstm) metrics, and a Train button that triggers
 * POST /dl/train and then refreshes both lists.
 */
export default function DL() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const {
    data: snapshot,
    isLoading: modelsLoading,
    error: modelsError,
    execute: fetchModels,
  } = useApi(getDlModels);
  const {
    data: metrics,
    isLoading: metricsLoading,
    error: metricsError,
    execute: fetchMetrics,
  } = useApi(getDlMetrics);
  const { isLoading: training, error: trainError, execute: train } = useApi(trainDlModels);
  // D3: keep the train outcome so failed family rows can surface their error text.
  const [trainOutcome, setTrainOutcome] = useState<DLTrainResult | null>(null);

  const loading = modelsLoading || metricsLoading;
  const error = modelsError ?? metricsError;

  useEffect(() => {
    if (!selectedLotteryId) return;
    void fetchModels(selectedLotteryId);
    void fetchMetrics(selectedLotteryId);
  }, [selectedLotteryId, fetchModels, fetchMetrics]);

  const refetch = () => {
    if (!selectedLotteryId) return;
    void fetchModels(selectedLotteryId);
    void fetchMetrics(selectedLotteryId);
  };

  const handleTrain = async () => {
    if (!selectedLotteryId || training) return;
    const result = await train(selectedLotteryId);
    if (result) {
      setTrainOutcome(result);
      refetch();
    }
  };

  const rows = [...(metrics ?? [])].sort(
    (a, b) => (FAMILY_ORDER[a.model_id] ?? 2) - (FAMILY_ORDER[b.model_id] ?? 2),
  );

  const renderContent = () => {
    if (!selectedLotteryId) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return <ErrorState message={error} onRetry={() => void refetch()} />;
    }
    if (loading) {
      return <Skeleton variant="card" />;
    }
    if (trainError) {
      return <ErrorState message={trainError} onRetry={() => void handleTrain()} />;
    }
    if (!snapshot && rows.length === 0) {
      return (
        <EmptyState
          message={NO_MODELS_MESSAGE}
          action={
            <button
              type="button"
              onClick={() => void handleTrain()}
              disabled={training}
              className={BUTTON_CLASS}
            >
              {training ? "Training…" : "Train"}
            </button>
          }
        />
      );
    }
    return (
      <div className="space-y-4">
        {snapshot ? <SnapshotSummary snapshot={snapshot} /> : null}
        {rows.length === 0 ? (
          <EmptyState message={NO_METRICS_MESSAGE} />
        ) : (
          <DataTable
            columns={metricColumns}
            rows={rows}
            rowKey={(row) => `${row.model_id}-${row.number}-${row.metric_name}`}
            caption="Deep learning metrics"
          />
        )}
        {trainOutcome?.results.some((row) => row.status === "failed") ? (
          <div aria-label="Training results" className="space-y-1 text-sm text-red-600">
            {trainOutcome.results
              .filter((row) => row.status === "failed")
              .map((row) => (
                <p key={row.family}>{`${row.family}: ${row.error ?? "unknown error"}`}</p>
              ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Deep Learning</h2>
          <p className="text-sm text-gray-500">
            Active deep learning snapshot and per-family metrics for the selected
            lottery.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleTrain()}
          disabled={!selectedLotteryId || training}
          aria-busy={training}
          className={BUTTON_CLASS}
        >
          {training ? "Training…" : "Train"}
        </button>
      </div>
      <section
        aria-label="Deep learning results"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </section>
    </div>
  );
}
