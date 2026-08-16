import { useEffect, useMemo, type ReactNode } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FrequencyChart from "../charts/FrequencyChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getDraws } from "../services/draws";
import { getFrequencies } from "../services/statistics";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Draw } from "../types/draw";
import type { FrequencyRow } from "../types/statistics";

const DRAW_WINDOW = 100;
const TREND_DRAWS = 20;
const HOT_COLD_COUNT = 5;
const NO_LOTTERY_MESSAGE = "Select a lottery to see its trends.";
const NO_DATA_MESSAGE = "No draws available for this lottery.";
const SERIES_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#d97706", "#059669"];

/** Count occurrences of each number across the given draws. */
function countNumbers(draws: Draw[]): Map<number, number> {
  const counts = new Map<number, number>();
  for (const draw of draws) {
    for (const num of draw.numbers) {
      counts.set(num.number, (counts.get(num.number) ?? 0) + 1);
    }
  }
  return counts;
}

/** Top-N most (asc=false) or least (asc=true) frequent numbers in a window. */
function extremeFrequencies(counts: Map<number, number>, asc: boolean): FrequencyRow[] {
  return [...counts.entries()]
    .map(([number, count]) => ({ number, count }))
    .sort((a, b) => (asc ? a.count - b.count : b.count - a.count))
    .slice(0, HOT_COLD_COUNT);
}

/** Rolling cumulative frequency of the hot numbers across the last draws. */
function rollingTrend(draws: Draw[], hotNumbers: number[]): Record<string, number>[] {
  const hotSet = new Set(hotNumbers);
  const running = new Map<number, number>();
  return [...draws]
    .sort((a, b) => a.draw_number - b.draw_number)
    .slice(-TREND_DRAWS)
    .map((draw) => {
      for (const num of draw.numbers) {
        if (hotSet.has(num.number)) {
          running.set(num.number, (running.get(num.number) ?? 0) + 1);
        }
      }
      const point: Record<string, number> = { draw: draw.draw_number };
      for (const number of hotNumbers) {
        point[String(number)] = running.get(number) ?? 0;
      }
      return point;
    });
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="rounded-md border border-gray-200 bg-white p-4">
      <h3 id={id} className="mb-3 text-sm font-semibold text-gray-900">
        {title}
      </h3>
      {children}
    </section>
  );
}

function FrequencyList({ title, rows }: { title: string; rows: FrequencyRow[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h4>
      <ol className="space-y-1">
        {rows.map((row, index) => (
          <li
            key={row.number}
            className="flex items-center justify-between rounded px-2 py-1 text-sm odd:bg-gray-50"
          >
            <span className="w-6 text-gray-400">{index + 1}</span>
            <span className="font-medium text-gray-900">{row.number}</span>
            <span className="text-gray-500">{row.count}×</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Rolling-frequency line chart of the hot numbers over the last draws. */
function TrendChart({ data, numbers }: { data: Record<string, number>[]; numbers: number[] }) {
  return (
    <div
      className="w-full"
      style={{ minHeight: 240 }}
      role="img"
      aria-label="Rolling frequency trend of hot numbers over recent draws"
    >
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="draw" tick={{ fill: "#4b5563", fontSize: 12 }} />
          <YAxis tick={{ fill: "#4b5563", fontSize: 12 }} />
          <Tooltip />
          {numbers.map((number, index) => (
            <Line
              key={number}
              type="monotone"
              dataKey={String(number)}
              stroke={SERIES_COLORS[index % SERIES_COLORS.length] ?? "#2563eb"}
              strokeWidth={2}
              dot={{ r: 2 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Trends page (Tendencias). Composes existing endpoints — recent draws and the
 * statistics frequency snapshot — into functional trend views: rolling frequency
 * of the hot numbers, hot/cold number lists, and the overall window distribution.
 * When the frequency snapshot is missing it derives frequencies from the draws.
 */
export default function Trends() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: draws,
    isLoading: drawsLoading,
    error: drawsError,
    execute: fetchDraws,
  } = useApi(getDraws);
  const { data: freqData, execute: fetchFrequencies } = useApi(getFrequencies);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    void fetchDraws(selectedLotteryCode, 1, DRAW_WINDOW);
    void fetchFrequencies(selectedLotteryCode);
  }, [selectedLotteryCode, fetchDraws, fetchFrequencies]);

  const windowCounts = useMemo(() => countNumbers(draws ?? []), [draws]);
  const hot = useMemo(() => extremeFrequencies(windowCounts, false), [windowCounts]);
  const cold = useMemo(() => extremeFrequencies(windowCounts, true), [windowCounts]);
  const trendData = useMemo(
    () => rollingTrend(draws ?? [], hot.map((row) => row.number)),
    [draws, hot],
  );
  const windowFrequencies = useMemo(
    () =>
      [...windowCounts.entries()].map(([number, count]) => ({ number, count })),
    [windowCounts],
  );
  const overallFrequencies =
    freqData?.frequencies.length ? freqData.frequencies : windowFrequencies;

  const renderContent = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (drawsError) {
      return (
        <ErrorState
          message={drawsError}
          onRetry={() => void fetchDraws(selectedLotteryCode, 1, DRAW_WINDOW)}
        />
      );
    }
    if (drawsLoading) return <Skeleton variant="card" />;
    if ((draws ?? []).length === 0) return <EmptyState message={NO_DATA_MESSAGE} />;
    return (
      <div className="space-y-6">
        <Section id="trends-trend-title" title="Recent trend">
          <TrendChart data={trendData} numbers={hot.map((row) => row.number)} />
        </Section>
        <div className="grid gap-6 lg:grid-cols-2">
          <Section id="trends-hot-title" title="Hot numbers">
            <FrequencyList title="Most frequent" rows={hot} />
          </Section>
          <Section id="trends-cold-title" title="Cold numbers">
            <FrequencyList title="Least frequent" rows={cold} />
          </Section>
        </div>
        <Section id="trends-frequency-title" title="Overall frequency">
          <FrequencyChart rows={overallFrequencies} />
        </Section>
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Trends</h2>
        <p className="text-sm text-gray-500">
          Rolling frequency and hot/cold numbers derived from recent draws and the
          frequency snapshot for the selected lottery.
        </p>
      </div>
      {renderContent()}
    </div>
  );
}