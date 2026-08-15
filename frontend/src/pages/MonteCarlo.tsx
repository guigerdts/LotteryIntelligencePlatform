import { useEffect, useState } from "react";
import DistributionChart from "../charts/DistributionChart";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { generateProbability, getProbabilities } from "../services/probability";
import { useLotteryStore } from "../store/useLotteryStore";
import type { ProbabilitySnapshot, ProbRow } from "../types/probability";

const NO_LOTTERY_MESSAGE = "Select a lottery to see probability rows.";
const NO_DATA_MESSAGE =
  "No probabilities available for this lottery. Click Generate to compute them.";
const BUTTON_CLASS =
  "rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

const probabilityColumns: DataColumn<ProbRow>[] = [
  { key: "model_id", label: "Model", sortable: true },
  { key: "subject", label: "Subject", sortable: true },
  { key: "draw_number", label: "Draw", sortable: true },
  { key: "value", label: "Probability", sortable: true },
];

function SnapshotSummary({ snapshot }: { snapshot: ProbabilitySnapshot }) {
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
      <span>
        Snapshot <span className="font-medium text-gray-900">#{snapshot.snapshot_id}</span>
      </span>
      <span>
        Range{" "}
        <span className="font-medium text-gray-900">
          {snapshot.draws_from}–{snapshot.draws_to}
        </span>
      </span>
      <span>
        Draws <span className="font-medium text-gray-900">{snapshot.draw_count}</span>
      </span>
      <span>
        Models <span className="font-medium text-gray-900">{snapshot.model_set}</span>
      </span>
    </p>
  );
}

/**
 * Monte Carlo page (Avanzado). Triggers probability generation via
 * POST /probability/generate and renders the resulting probability rows from
 * GET /probability/{code}/probabilities as a table with a distribution chart.
 */
export default function MonteCarlo() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: list,
    isLoading: loading,
    error,
    execute: fetchProbabilities,
  } = useApi(getProbabilities);
  const {
    isLoading: generating,
    error: generateError,
    execute: generate,
  } = useApi(generateProbability);
  const [snapshot, setSnapshot] = useState<ProbabilitySnapshot | null>(null);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    setSnapshot(null);
    void fetchProbabilities(selectedLotteryCode);
  }, [selectedLotteryCode, fetchProbabilities]);

  const handleGenerate = async () => {
    if (!selectedLotteryCode || generating) return;
    const result = await generate(selectedLotteryCode);
    if (result) setSnapshot(result);
    void fetchProbabilities(selectedLotteryCode);
  };

  const renderContent = () => {
    if (!selectedLotteryCode) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return (
        <ErrorState
          message={error}
          onRetry={() => void fetchProbabilities(selectedLotteryCode)}
        />
      );
    }
    if (loading) {
      return <Skeleton variant="card" />;
    }
    if (generateError) {
      return <ErrorState message={generateError} onRetry={() => void handleGenerate()} />;
    }
    const rows = list?.probabilities ?? [];
    if (rows.length === 0) {
      return (
        <EmptyState
          message={NO_DATA_MESSAGE}
          action={
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={generating}
              className={BUTTON_CLASS}
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          }
        />
      );
    }
    return (
      <div className="space-y-4">
        {snapshot ? <SnapshotSummary snapshot={snapshot} /> : null}
        <DataTable
          columns={probabilityColumns}
          rows={rows}
          rowKey={(row) => `${row.model_id}-${row.subject}-${row.draw_number}`}
          caption="Probability rows"
        />
        <DistributionChart
          rows={rows.map((row) => ({ subject: row.subject, value: row.value }))}
        />
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Monte Carlo</h2>
          <p className="text-sm text-gray-500">
            Probability rows for the selected lottery.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={!selectedLotteryCode || generating}
          aria-busy={generating}
          className={BUTTON_CLASS}
        >
          {generating ? "Generating…" : "Generate"}
        </button>
      </div>
      <section
        aria-label="Probability results"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </section>
    </div>
  );
}