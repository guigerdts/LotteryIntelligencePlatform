import { useEffect, useState, type FormEvent } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { createExperiment, listExperiments } from "../services/experiments";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Experiment } from "../types/experiment";

const NO_LOTTERY_MESSAGE = "Select a lottery to see experiments.";
const NO_EXPERIMENTS_MESSAGE = "No experiments yet.";
const BUTTON_CLASS =
  "rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";
const INPUT_CLASS =
  "rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

const columns: DataColumn<Experiment>[] = [
  { key: "name", label: "Name", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "version", label: "Version", sortable: true },
  { key: "created_at", label: "Created", sortable: true, sortValue: (row) => row.created_at },
  { key: "description", label: "Description" },
];

/**
 * Experiments page (ML). Lists experiments for the global lottery and creates
 * new experiments inline. Run and Compare actions are deferred to a later
 * slice: they need a valid engine snapshot id that the UI cannot know here.
 */
export default function Experiments() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const {
    data,
    isLoading,
    error,
    execute: fetchExperiments,
  } = useApi(listExperiments);
  const {
    isLoading: creating,
    error: createError,
    execute: createExperimentFn,
  } = useApi(createExperiment);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (!selectedLotteryId) return;
    void fetchExperiments(selectedLotteryId);
  }, [selectedLotteryId, fetchExperiments]);

  const refetch = () => {
    if (!selectedLotteryId) return;
    void fetchExperiments(selectedLotteryId);
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedLotteryId || creating) return;
    const trimmedName = name.trim();
    if (!trimmedName) return;
    const result = await createExperimentFn(
      selectedLotteryId,
      trimmedName,
      description.trim() || undefined,
    );
    if (result) {
      setName("");
      setDescription("");
      refetch();
    }
  };

  const renderContent = () => {
    if (!selectedLotteryId) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return <ErrorState message={error} onRetry={() => void refetch()} />;
    }
    if (isLoading) {
      return <Skeleton variant="card" />;
    }
    const rows = data ?? [];
    if (rows.length === 0) {
      return <EmptyState message={NO_EXPERIMENTS_MESSAGE} />;
    }
    return (
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => String(row.experiment_id)}
        caption="Experiments"
      />
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Experiments</h2>
        <p className="text-sm text-gray-500">
          Experiment tracking for the selected lottery.
        </p>
      </div>
      <section
        aria-label="Create experiment"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        <form onSubmit={(event) => void handleCreate(event)} className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-900">Create experiment</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="experiment-name"
                className="mb-1 block text-sm font-medium text-gray-700"
              >
                Name
              </label>
              <input
                id="experiment-name"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={200}
                className={`${INPUT_CLASS} w-full`}
              />
            </div>
            <div>
              <label
                htmlFor="experiment-description"
                className="mb-1 block text-sm font-medium text-gray-700"
              >
                Description
              </label>
              <input
                id="experiment-description"
                type="text"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={1000}
                className={`${INPUT_CLASS} w-full`}
              />
            </div>
          </div>
          {createError ? (
            <p role="alert" className="text-sm text-red-600">
              {createError}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={!selectedLotteryId || creating}
            aria-busy={creating}
            className={BUTTON_CLASS}
          >
            {creating ? "Creating…" : "Create experiment"}
          </button>
        </form>
      </section>
      <section
        aria-label="Experiment list"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </section>
    </div>
  );
}