import { useEffect } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getMetrics, getModels, trainModels } from "../services/ml";
import { useLotteryStore } from "../store/useLotteryStore";
import type { MLMetrics, MLSnapshot } from "../types/ml";

const NO_LOTTERY_MESSAGE = "Select a lottery to see models.";
const NO_MODELS_MESSAGE = "No models trained for this lottery yet. Click Train to generate them.";
const NO_METRICS_MESSAGE = "No metrics available for this lottery.";
const BUTTON_CLASS =
  "rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

const metricColumns: DataColumn<MLMetrics>[] = [
  { key: "model_id", label: "Model", sortable: true },
  { key: "number", label: "Number", sortable: true },
  { key: "metric_name", label: "Metric", sortable: true },
  { key: "value", label: "Value", sortable: true, sortValue: (row) => row.value },
];

function SnapshotSummary({ snapshot }: { snapshot: MLSnapshot }) {
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
      <span>
        Snapshot <span className="font-medium text-gray-900">#{snapshot.id}</span>
      </span>
      <span>
        Model set <span className="font-medium text-gray-900">{snapshot.model_set}</span>
      </span>
      <span>
        Version <span className="font-medium text-gray-900">{snapshot.version}</span>
      </span>
      <span>
        Status <span className="font-medium text-gray-900">{snapshot.status}</span>
      </span>
      <span>
        Checksum <span className="font-mono text-xs text-gray-900">{snapshot.checksum}</span>
      </span>
    </p>
  );
}

/**
 * Models page (ML). Shows the active ML snapshot for the global lottery, its
 * persisted metrics, and a Train button that triggers POST /ml/train and then
 * refreshes both lists.
 */
export default function Models() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const {
    data: snapshot,
    isLoading: modelsLoading,
    error: modelsError,
    execute: fetchModels,
  } = useApi(getModels);
  const {
    data: metrics,
    isLoading: metricsLoading,
    error: metricsError,
    execute: fetchMetrics,
  } = useApi(getMetrics);
  const { isLoading: training, error: trainError, execute: train } = useApi(trainModels);

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
    if (result) refetch();
  };

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
    const rows = metrics ?? [];
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
            caption="Model metrics"
          />
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Models</h2>
          <p className="text-sm text-gray-500">
            Active model families and metrics for the selected lottery.
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
        aria-label="Model results"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </section>
    </div>
  );
}
