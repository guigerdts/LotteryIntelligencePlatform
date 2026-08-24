import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface AverageSeriesRow {
  series_key: string;
  mean: number | null;
  non_null_count: number;
}

export interface AverageChartProps {
  series: AverageSeriesRow[];
}

type MeanRow = AverageSeriesRow & { mean: number };

/** Bar chart of the average gap per series (source: statistics averages). */
export default function AverageChart({ series }: AverageChartProps) {
  const data: { series: string; mean: number }[] = series
    .filter((row): row is MeanRow => row.mean !== null && row.mean !== undefined)
    .map((row) => ({ series: row.series_key, mean: row.mean }));

  return (
    <div
      className="w-full"
      style={{ minHeight: 240 }}
      role="img"
      aria-label="Average gap per series"
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="series" tick={{ fill: "#4b5563", fontSize: 12 }} />
          <YAxis tick={{ fill: "#4b5563", fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="mean" fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
