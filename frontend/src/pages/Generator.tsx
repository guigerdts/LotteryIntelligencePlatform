import { useState, type FormEvent } from "react";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { AppError } from "../services/api";
import { generateCombinations } from "../services/gen";
import { useLotteryStore } from "../store/useLotteryStore";
import type { CombinationRow, GenerationResult } from "../types/gen";

const NO_LOTTERY_MESSAGE = "Select a lottery to generate combinations.";
const DEFAULT_COUNT = 10;
const FIELD_CLASS =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100";

const GEN_ERROR_MESSAGES: Record<string, string> = {
  GEN_NO_SELECTION: "No active selection for this lottery.",
  GEN_NO_DISTRIBUTION: "No distribution available for this lottery.",
  GEN_LOTTERY_NOT_FOUND: "Lottery not found.",
  GEN_COUNT_INVALID: "Count must be between 1 and 100.",
  GEN_SNAPSHOT_NOT_FOUND: "Snapshot not found.",
  GEN_DUPLICATE_SNAPSHOT: "A snapshot with this fingerprint already exists.",
  GEN_SPACE_EXHAUSTED: "Generation space exhausted.",
};

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

interface GenerateParams {
  lottery_id: number;
  count: number;
  seed?: number;
  selection_id?: number;
}

/** Map a backend GEN_* error to a user-friendly message. */
function mapGenError(err: unknown): string {
  if (err instanceof AppError) {
    const message = GEN_ERROR_MESSAGES[err.code];
    if (message) {
      return message;
    }
  }
  return err instanceof Error ? err.message : "Unknown error";
}

/** Wrapped generate that surfaces mapped GEN_* messages to the useApi hook. */
async function generateWithMessages(params: GenerateParams): Promise<GenerationResult> {
  try {
    return await generateCombinations(params);
  } catch (err) {
    throw new Error(mapGenError(err));
  }
}

function ResultPanel({ result }: { result: GenerationResult }) {
  return (
    <div aria-live="polite" className="space-y-3">
      <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
        <span>
          Snapshot <span className="font-medium text-gray-900">#{result.snapshot_id}</span>
        </span>
        <span>
          Seed <span className="font-medium text-gray-900">{result.seed}</span>
        </span>
        <span>
          Status <span className="font-medium text-gray-900">{result.status}</span>
        </span>
        <span>
          Fingerprint <span className="font-medium text-gray-900">{result.fingerprint}</span>
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
 * Generator page (Generador). Inline form → POST /gen/generate → inline result
 * on the same page. Maps every GEN_* error code to a user-friendly message and
 * covers no-selection, loading, error+retry and success states.
 */
export default function Generator() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const [countInput, setCountInput] = useState("");
  const [seedInput, setSeedInput] = useState("");
  const [selectionInput, setSelectionInput] = useState("");
  const { data, isLoading, error, execute } = useApi(generateWithMessages);

  const generating = isLoading;
  const fieldDisabled = !selectedLotteryId || generating;

  const runGenerate = () => {
    if (!selectedLotteryId || generating) return;
    const count = countInput === "" ? DEFAULT_COUNT : Number(countInput);
    const seed = seedInput === "" ? undefined : Number(seedInput);
    const selectionId = selectionInput === "" ? undefined : Number(selectionInput);
    void execute({ lottery_id: selectedLotteryId, count, seed, selection_id: selectionId });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    runGenerate();
  };

  const renderResult = () => {
    if (!selectedLotteryId) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return <ErrorState message={error} onRetry={runGenerate} />;
    }
    if (generating) {
      return <Skeleton variant="card" />;
    }
    if (data) {
      return <ResultPanel result={data} />;
    }
    return (
      <p className="text-sm text-gray-500">
        Set the parameters and click Generate to build combinations inline.
      </p>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Generator</h2>
        <p className="text-sm text-gray-500">
          Generate number combinations for the selected lottery.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label
              htmlFor="gen-count"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Count (1–100)
            </label>
            <input
              id="gen-count"
              type="number"
              min={1}
              max={100}
              placeholder="10"
              value={countInput}
              onChange={(event) => setCountInput(event.target.value)}
              disabled={fieldDisabled}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor="gen-seed"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Seed
            </label>
            <input
              id="gen-seed"
              type="number"
              placeholder="Optional"
              value={seedInput}
              onChange={(event) => setSeedInput(event.target.value)}
              disabled={fieldDisabled}
              className={FIELD_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor="gen-selection"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Selection ID
            </label>
            <input
              id="gen-selection"
              type="number"
              placeholder="Optional"
              value={selectionInput}
              onChange={(event) => setSelectionInput(event.target.value)}
              disabled={fieldDisabled}
              className={FIELD_CLASS}
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={fieldDisabled}
          aria-busy={generating}
          className="mt-4 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {generating ? "Generating…" : "Generate"}
        </button>
      </form>

      <section
        aria-label="Generation result"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderResult()}
      </section>
    </div>
  );
}
