import { useMemo, type ReactElement } from "react";

export interface HeatmapChartProps {
  rows: { subject: string; value: number }[];
  numbers?: number[];
}

const CELL = 20;
const GAP = 2;
const LABEL = 24;
const LIGHT: [number, number, number] = [239, 246, 255];
const DARK: [number, number, number] = [29, 78, 216];
const DARK_TEXT = "#0f172a";
const LIGHT_TEXT = "#ffffff";
const ARIA_LABEL = "Co-occurrence heatmap by number";

function parsePair(subject: string): [number, number] | null {
  const parts = subject.split("-");
  if (parts.length !== 2) return null;
  const i = Number(parts[0]);
  const j = Number(parts[1]);
  return Number.isFinite(i) && Number.isFinite(j) ? [i, j] : null;
}

function blend(t: number): string {
  const mix = (lo: number, hi: number) => Math.round(lo + (hi - lo) * t);
  return `rgb(${mix(LIGHT[0], DARK[0])}, ${mix(LIGHT[1], DARK[1])}, ${mix(LIGHT[2], DARK[2])})`;
}

function readableFill(t: number): string {
  const lum =
    (0.2126 * (LIGHT[0] + (DARK[0] - LIGHT[0]) * t) +
      0.7152 * (LIGHT[1] + (DARK[1] - LIGHT[1]) * t) +
      0.0722 * (LIGHT[2] + (DARK[2] - LIGHT[2]) * t)) /
    255;
  return lum > 0.35 ? DARK_TEXT : LIGHT_TEXT;
}

interface GridData {
  size: number;
  matrix: (number | null)[][];
  min: number;
  max: number;
}

/** Custom SVG heatmap grid of number-pair co-occurrence counts (blue intensity). */
export default function HeatmapChart({ rows, numbers }: HeatmapChartProps) {
  const grid = useMemo<GridData>(() => {
    let size = numbers && numbers.length ? Math.max(...numbers) : 0;
    for (const row of rows) {
      const pair = parsePair(row.subject);
      if (pair) size = Math.max(size, pair[0], pair[1]);
    }
    if (size <= 0) return { size: 0, matrix: [], min: 0, max: 0 };
    const matrix: (number | null)[][] = Array.from({ length: size }, () =>
      Array.from({ length: size }, () => null),
    );
    let min = Infinity;
    let max = -Infinity;
    for (const row of rows) {
      const pair = parsePair(row.subject);
      if (!pair || pair[0] > size || pair[1] > size) continue;
      const a = matrix[pair[0] - 1];
      const b = matrix[pair[1] - 1];
      if (a && b) {
        a[pair[1] - 1] = row.value;
        b[pair[0] - 1] = row.value;
      }
      min = Math.min(min, row.value);
      max = Math.max(max, row.value);
    }
    return { size, matrix, min: min === Infinity ? 0 : min, max: max === -Infinity ? 0 : max };
  }, [rows, numbers]);

  if (grid.size === 0) {
    return <div role="img" aria-label={ARIA_LABEL} />;
  }

  const cell = CELL + GAP;
  const width = LABEL + grid.size * cell + GAP;
  const height = LABEL + grid.size * cell + GAP;
  const span = Math.max(grid.max - grid.min, 1);
  const nodes: ReactElement[] = [];
  for (let i = 0; i < grid.size; i += 1) {
    for (let j = 0; j < grid.size; j += 1) {
      const value = grid.matrix[i]?.[j] ?? null;
      const t = value === null ? 0 : (value - grid.min) / span;
      nodes.push(
        <rect key={`${i}-${j}`} x={LABEL + j * cell} y={LABEL + i * cell} width={CELL} height={CELL} rx={2} fill={value === null ? "#f3f4f6" : blend(t)}>
          {value === null ? null : <title>{`${i + 1}–${j + 1}: ${value}`}</title>}
        </rect>,
      );
      if (value !== null) {
        nodes.push(
          <text key={`t-${i}-${j}`} x={LABEL + j * cell + CELL / 2} y={LABEL + i * cell + CELL / 2} textAnchor="middle" dominantBaseline="central" fontSize={9} fill={readableFill(t)}>
            {value}
          </text>,
        );
      }
    }
  }

  return (
    <div className="w-full overflow-auto" role="img" aria-label={ARIA_LABEL}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxWidth: 640 }} role="presentation">
        {nodes}
      </svg>
    </div>
  );
}