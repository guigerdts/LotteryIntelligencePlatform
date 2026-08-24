import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface DistributionRow {
  subject: string;
  value: number | string;
}

export interface DistributionChartProps {
  rows: DistributionRow[];
}

function parseValue(value: number | string): number | undefined {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

/** Bar chart of a probability distribution per subject. */
export default function DistributionChart({ rows }: DistributionChartProps) {
  const data: { subject: string; value: number }[] = rows
    .map((row) => ({ subject: row.subject, value: parseValue(row.value) }))
    .filter((row): row is { subject: string; value: number } => row.value !== undefined);

  return (
    <div
      className="w-full"
      style={{ minHeight: 240 }}
      role="img"
      aria-label="Probability distribution per subject"
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="subject" tick={{ fill: "#4b5563", fontSize: 12 }} />
          <YAxis tick={{ fill: "#4b5563", fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
