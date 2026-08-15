import { useState, type FormEvent } from "react";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getBacktestResults, runBacktest } from "../services/backtesting";
import { useLotteryStore } from "../store/useLotteryStore";
import type { BacktestMetrics, BacktestRun } from "../types/backtesting";

const NO_LOTTERY_MESSAGE = "Select a lottery to run a backtest.";
const DEFAULT_TRAIN_YEARS = 5;
const DEFAULT_EVAL_COUNT = 100;
const DEFAULT_STEP_COUNT = 10;
const DEFAULT_MIN_TRAIN_DRAWS = 50;
const FIELD_CLASS =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100";

interface FieldConfig {
  id: string;
  label: string;
  type?: "text" | "number";
  min?: number;
  max?: number;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  fullWidth?: boolean;
}

const textField = (
  id: string,
  label: string,
  value: string,
  onChange: (value: string) => void,
  placeholder?: string,
  fullWidth?: boolean,
): FieldConfig => ({ id, label, value, onChange, placeholder, fullWidth });

const numberField = (
  id: string,
  label: string,
  min: number,
  max: number | undefined,
  value: string,
  onChange: (value: string) => void,
  placeholder?: string,
): FieldConfig => ({ id, label, type: "number", min, max, value, onChange, placeholder });

function formatHitRate(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function MetricsGrid({ metrics }: { metrics: BacktestMetrics }) {
  const rows = [
    { label: "Hit rate", value: formatHitRate(metrics.hit_rate) },
    { label: "Average matches", value: metrics.average_matches.toFixed(2) },
    { label: "Consistency score", value: metrics.consistency_score.toFixed(2) },
    { label: "Draws evaluated", value: String(metrics.total_draws_evaluated) },
  ];
  return (
    <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {rows.map((row) => (
        <div key={row.label} className="rounded-md bg-gray-50 p-3">
          <dt className="text-xs uppercase tracking-wide text-gray-500">{row.label}</dt>
          <dd className="mt-1 text-lg font-semibold text-gray-900">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RunSummary({ run }: { run: BacktestRun }) {
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
      <span>
        Snapshot <span className="font-medium text-gray-900">#{run.snapshot_id}</span>
      </span>
      <span>
        Strategy <span className="font-medium text-gray-900">{run.strategy_id}</span>
      </span>
      <span>
        Status <span className="font-medium text-gray-900">{run.status}</span>
      </span>
      <span>
        Fingerprint <span className="font-medium text-gray-900">{run.fingerprint}</span>
      </span>
    </p>
  );
}

/**
 * Backtesting page (ML). Inline form → POST /backtesting/run → BacktestRun
 * summary plus aggregate metrics from GET /backtesting/results for the new
 * snapshot.
 */
export default function Backtesting() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const [strategyInput, setStrategyInput] = useState("");
  const [trainYearsInput, setTrainYearsInput] = useState(String(DEFAULT_TRAIN_YEARS));
  const [evalCountInput, setEvalCountInput] = useState(String(DEFAULT_EVAL_COUNT));
  const [stepCountInput, setStepCountInput] = useState(String(DEFAULT_STEP_COUNT));
  const [minTrainDrawsInput, setMinTrainDrawsInput] = useState(
    String(DEFAULT_MIN_TRAIN_DRAWS),
  );
  const [seedInput, setSeedInput] = useState("");
  const [snapshot, setSnapshot] = useState<BacktestRun | null>(null);
  const {
    data: result,
    isLoading: loadingResults,
    error: resultsError,
    execute: fetchResults,
  } = useApi(getBacktestResults);
  const {
    isLoading: running,
    error: runError,
    execute: run,
  } = useApi(runBacktest);

  const fieldDisabled = !selectedLotteryId || running;

  const fields: FieldConfig[] = [
    textField("bt-strategy", "Strategy ID", strategyInput, setStrategyInput, "e.g. uniform-weighted", true),
    numberField("bt-train-years", "Train years", 1, 50, trainYearsInput, setTrainYearsInput),
    numberField("bt-eval-count", "Eval count", 1, 52, evalCountInput, setEvalCountInput),
    numberField("bt-step-count", "Step count", 1, 52, stepCountInput, setStepCountInput),
    numberField("bt-min-draws", "Min train draws", 10, 5000, minTrainDrawsInput, setMinTrainDrawsInput),
    numberField("bt-seed", "Seed", 0, undefined, seedInput, setSeedInput, "Optional"),
  ];

  const handleRun = async () => {
    if (!selectedLotteryId || running) return;
    const params = {
      lottery_id: selectedLotteryId,
      strategy_id: strategyInput.trim(),
      train_years:
        trainYearsInput === "" ? DEFAULT_TRAIN_YEARS : Number(trainYearsInput),
      eval_count: evalCountInput === "" ? DEFAULT_EVAL_COUNT : Number(evalCountInput),
      step_count: stepCountInput === "" ? DEFAULT_STEP_COUNT : Number(stepCountInput),
      min_train_draws:
        minTrainDrawsInput === "" ? DEFAULT_MIN_TRAIN_DRAWS : Number(minTrainDrawsInput),
      ...(seedInput === "" ? {} : { seed: Number(seedInput) }),
    };
    const runResult = await run(params);
    if (runResult) {
      setSnapshot(runResult);
      void fetchResults(selectedLotteryId, runResult.snapshot_id);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handleRun();
  };

  const renderResult = () => {
    if (!selectedLotteryId) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (runError) {
      return <ErrorState message={runError} onRetry={() => void handleRun()} />;
    }
    if (running) {
      return <Skeleton variant="card" />;
    }
    if (snapshot && resultsError) {
      return (
        <ErrorState
          message={resultsError}
          onRetry={() => void fetchResults(selectedLotteryId, snapshot.snapshot_id)}
        />
      );
    }
    if (snapshot && loadingResults) {
      return <Skeleton variant="card" />;
    }
    if (snapshot && result) {
      return (
        <div aria-live="polite" className="space-y-4">
          <RunSummary run={snapshot} />
          <MetricsGrid metrics={result.aggregate_metrics} />
        </div>
      );
    }
    return (
      <p className="text-sm text-gray-500">
        Set the parameters and click Run Backtest to evaluate a strategy on this
        lottery.
      </p>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Backtesting</h2>
        <p className="text-sm text-gray-500">
          Evaluate a strategy against historical draws for the selected lottery.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          {fields.map((field) => (
            <div
              key={field.id}
              className={field.fullWidth ? "sm:col-span-3" : ""}
            >
              <label
                htmlFor={field.id}
                className="mb-1 block text-sm font-medium text-gray-700"
              >
                {field.label}
              </label>
              <input
                id={field.id}
                type={field.type ?? "text"}
                min={field.min}
                max={field.max}
                placeholder={field.placeholder}
                value={field.value}
                onChange={(event) => field.onChange(event.target.value)}
                disabled={fieldDisabled}
                className={FIELD_CLASS}
              />
            </div>
          ))}
        </div>
        <button
          type="submit"
          disabled={fieldDisabled}
          aria-busy={running}
          className="mt-4 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {running ? "Running…" : "Run Backtest"}
        </button>
      </form>

      <section
        aria-label="Backtest result"
        className="rounded-md border border-gray-200 bg-white p-4"
      >
        {renderResult()}
      </section>
    </div>
  );
}