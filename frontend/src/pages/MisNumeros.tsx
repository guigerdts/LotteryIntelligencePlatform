import { useState } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import TierTable from "../components/TierTable";
import { useApi } from "../hooks/useApi";
import { AppError } from "../services/api";
import { runNumbersPipeline } from "../services/pipeline";
import { useLotteryStore } from "../store/useLotteryStore";
import type { CombinationRow, GenerationResult } from "../types/gen";
import type { PipelineRunResult, PipelineStageResult } from "../types/pipeline";

const NO_LOTTERY_MESSAGE = "Select a lottery to generate your numbers.";
const IDLE_HINT = "Click Generate numbers to run the full analysis chain and build your ticket.";
/** Owner decision: every ticket is valid for BOTH draws; no toggle exists. */
const DUAL_DRAW_LABEL = "Un boleto, dos sorteos (Baloto + Revancha)";
const DISCLAIMER_TEXT =
  "Combinations are statistically informed by historical draws, but official draws remain completely random: no method improves prediction odds and no outcome is promised.";
/** Default combination count sent in the payload (R4/D11). */
const DEFAULT_COUNT = 5;
const BUTTON_CLASS =
  "rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";
const FIELD_CLASS =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100";

/** Combination columns survive from Generator.tsx: super_number/score included. */
const combinationColumns: DataColumn<CombinationRow>[] = [
  { key: "position", label: "#", sortable: true },
  {
    key: "numbers",
    label: "Numbers",
    render: (row) => row.numbers.join(" - "),
  },
  {
    key: "super_number",
    label: "Super",
    render: (row) => row.super_number ?? "—",
  },
  {
    key: "score",
    label: "Score",
    render: (row) => row.score?.toFixed(2) ?? "—",
  },
];

/** Map a backend pipeline error to a user-friendly message. */
function mapPipelineError(err: unknown): string {
  if (err instanceof AppError && err.code === "PIPE_STAGE_FAILED") {
    return `The chain stopped at a failed stage: ${err.message}`;
  }
  return err instanceof Error ? err.message : "Unknown error";
}

/** Wrapped orchestrator call that surfaces mapped messages to the useApi hook. */
async function runWithMessages(params: {
  lottery_id: number;
  count?: number;
}): Promise<PipelineRunResult> {
  try {
    return await runNumbersPipeline(params);
  } catch (err) {
    throw new Error(mapPipelineError(err));
  }
}

/** Ordered per-stage report rendered straight from the response (R2). */
function StageReport({ stages }: { stages: PipelineStageResult[] }) {
  return (
    <ol aria-label="Pipeline stages" className="space-y-1 text-sm">
      {stages.map((stage) => (
        <li
          key={stage.name}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-gray-100 px-3 py-1.5"
        >
          <span className="font-mono text-xs font-medium text-gray-900">{stage.name}</span>
          <span
            data-status={stage.status}
            className={
              stage.status === "failed"
                ? "text-xs font-semibold text-red-700"
                : stage.status === "skipped"
                  ? "text-xs text-gray-500"
                  : "text-xs font-semibold text-green-700"
            }
          >
            {stage.status}
          </span>
          <span className="text-xs text-gray-400">{stage.detail}</span>
          {stage.status === "failed" ? (
            <span role="alert" className="w-full text-xs text-red-700">
              {stage.error_code}: {stage.detail}
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

/** Ticket presentation: dual-draw label plus scored combinations (R3). */
function TicketCards({ result }: { result: GenerationResult }) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold text-gray-900">{DUAL_DRAW_LABEL}</p>
      <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
        <span>
          Snapshot <span className="font-medium text-gray-900">#{result.snapshot_id}</span>
        </span>
        <span>
          Seed <span className="font-medium text-gray-900">{result.seed}</span>
        </span>
        <span>
          Fingerprint <span className="font-mono text-xs text-gray-900">{result.fingerprint}</span>
        </span>
      </p>
      <DataTable
        columns={combinationColumns}
        rows={result.combinations}
        rowKey={(row) => String(row.position)}
        caption="Generated combinations"
      />
    </div>
  );
}

/**
 * Mis Números page. One CTA runs the whole POST /pipeline/numbers chain; the
 * busy state holds for the entire minutes-scale request and the result renders
 * straight from the response — nothing is refetched afterwards.
 */
export default function MisNumeros() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const [countInput, setCountInput] = useState(String(DEFAULT_COUNT));
  const { data, isLoading, error, execute } = useApi(runWithMessages);

  const running = isLoading;

  const runPipeline = () => {
    if (!selectedLotteryId || running) return;
    void execute({ lottery_id: selectedLotteryId, count: Number(countInput) });
  };

  const renderContent = () => {
    if (!selectedLotteryId) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return <ErrorState message={error} onRetry={runPipeline} />;
    }
    if (running) {
      return (
        <div aria-busy="true" className="space-y-3">
          <p aria-live="polite" className="text-sm text-gray-600">
            Running the full analysis chain — this can take several minutes.
          </p>
          <Skeleton variant="card" />
        </div>
      );
    }
    if (data) {
      return (
        <div className="space-y-4">
          <StageReport stages={data.stages} />
          {data.result ? (
            <TicketCards result={data.result} />
          ) : (
            <p className="text-sm text-red-700">
              The chain stopped before generating combinations.
            </p>
          )}
        </div>
      );
    }
    return <p className="text-sm text-gray-500">{IDLE_HINT}</p>;
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Mis Números</h2>
          <p className="text-sm text-gray-500">
            One request runs stats → features → ml → dl → backtesting → rank → select → generate for
            the selected lottery.
          </p>
        </div>
        <button
          type="button"
          onClick={runPipeline}
          disabled={!selectedLotteryId || running}
          aria-busy={running}
          className={BUTTON_CLASS}
        >
          {running ? "Running pipeline…" : "Generate numbers"}
        </button>
      </div>

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <label htmlFor="mis-numeros-count" className="mb-1 block text-sm font-medium text-gray-700">
          Count
        </label>
        <input
          id="mis-numeros-count"
          type="number"
          min={1}
          max={100}
          value={countInput}
          onChange={(event) => setCountInput(event.target.value)}
          disabled={!selectedLotteryId || running}
          className={`${FIELD_CLASS} max-w-32`}
        />
      </div>

      <section
        aria-label="Mis números results"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderContent()}
      </section>

      <section
        aria-label="Official prize tiers reference"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        <TierTable />
      </section>

      <footer className="rounded-md border border-amber-200 bg-amber-50 p-4">
        <p className="text-sm text-amber-800">{DISCLAIMER_TEXT}</p>
      </footer>
    </div>
  );
}
