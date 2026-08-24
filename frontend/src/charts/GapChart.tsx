import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { GapRow } from "../types/statistics";

export interface GapChartProps {
  rows: GapRow[];
}

type SafeGapRow = {
  number: number;
  avg_gap?: number;
  min_gap?: number;
  max_gap?: number;
};

/** Line chart of average gap per number with a min-max range band. */
export default function GapChart({ rows }: GapChartProps) {
  const data: SafeGapRow[] = rows.map((row) => ({
    number: row.number,
    avg_gap: row.avg_gap ?? undefined,
    min_gap: row.min_gap ?? undefined,
    max_gap: row.max_gap ?? undefined,
  }));

  return (
    <div
      className="w-full"
      style={{ minHeight: 240 }}
      role="img"
      aria-label="Gap analysis per number with min-max range"
    >
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="number" tick={{ fill: "#4b5563", fontSize: 12 }} />
          <YAxis tick={{ fill: "#4b5563", fontSize: 12 }} />
          <Tooltip />
          <Area
            dataKey={(row: SafeGapRow) => [row.min_gap, row.max_gap]}
            fill="#bfdbfe"
            stroke="#93c5fd"
            fillOpacity={0.5}
          />
          <Line
            dataKey="avg_gap"
            stroke="#1d4ed8"
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
