import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FrequencyRow } from "../types/statistics";

export interface FrequencyChartProps {
  rows: FrequencyRow[];
}

/** Bar chart of draw frequency per number (source: statistics frequencies). */
export default function FrequencyChart({ rows }: FrequencyChartProps) {
  return (
    <div
      className="w-full"
      style={{ minHeight: 240 }}
      role="img"
      aria-label="Frequency distribution per number"
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="number" tick={{ fill: "#4b5563", fontSize: 12 }} />
          <YAxis tick={{ fill: "#4b5563", fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}