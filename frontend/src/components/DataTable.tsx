import { useMemo, useState, type ReactNode } from "react";
import Skeleton from "./Skeleton";

/**
 * Column definition for a DataTable. `key` addresses the source field (or a
 * stable identifier when `render` provides custom cell content), `label` is the
 * column header text. `sortable` enables click-to-sort using either `sortValue`
 * or the raw `key` value.
 */
export interface DataColumn<T> {
  key: string;
  label: string;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  loading?: boolean;
  loadingRows?: number;
  emptyMessage?: string;
}

const DEFAULT_EMPTY_MESSAGE = "No hay datos disponibles para esta lotería.";

const DEFAULT_EMPTY_CELL = "—";

function cellValue(row: unknown, key: string): string {
  const value = (row as Record<string, unknown>)[key];
  if (value === null || value === undefined) {
    return DEFAULT_EMPTY_CELL;
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function sortValueFor<T>(row: T, column: DataColumn<T>): string | number {
  if (column.sortValue) {
    return column.sortValue(row);
  }
  return cellValue(row, column.key);
}

function renderCell<T>(row: T, column: DataColumn<T>): ReactNode {
  if (column.render) {
    return column.render(row);
  }
  return cellValue(row, column.key);
}

/**
 * Generic, typed data table with sorting and built-in loading / empty states.
 * Always renders a `<caption>` for screen readers and `scope="col"` on column
 * headers; sortable columns become buttons with an `aria-sort` column header.
 */
export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  loading = false,
  loadingRows = 5,
  emptyMessage = DEFAULT_EMPTY_MESSAGE,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const handleSort = (key: string) => {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir("asc");
      return;
    }
    setSortDir((current) => (current === "asc" ? "desc" : "asc"));
  };

  const sortedRows = useMemo(() => {
    if (!sortKey) {
      return rows;
    }
    const column = columns.find((candidate) => candidate.key === sortKey);
    if (!column || !column.sortable) {
      return rows;
    }
    const direction = sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = sortValueFor(a, column);
      const right = sortValueFor(b, column);
      if (left < right) {
        return -direction;
      }
      if (left > right) {
        return direction;
      }
      return 0;
    });
  }, [rows, columns, sortKey, sortDir]);

  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead className="border-b border-border bg-surface-2 text-xs uppercase tracking-wide text-ink-2">
        <tr>
          {columns.map((column) => {
            const isSorted = sortKey === column.key;
            return (
              <th
                key={column.key}
                scope="col"
                aria-sort={isSorted ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
                className="px-3 py-2 font-semibold"
              >
                {column.sortable ? (
                  <button
                    type="button"
                    onClick={() => handleSort(column.key)}
                    className="inline-flex items-center gap-1 rounded font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    {column.label}
                    <span aria-hidden="true">
                      {isSorted ? (sortDir === "asc" ? "↑" : "↓") : ""}
                    </span>
                  </button>
                ) : (
                  column.label
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {loading ? (
          Array.from({ length: loadingRows }, (_, index) => (
            <tr key={index} className="border-b border-border">
              {columns.map((column) => (
                <td key={column.key} className="px-3 py-2">
                  <Skeleton variant="text" />
                </td>
              ))}
            </tr>
          ))
        ) : sortedRows.length === 0 ? (
          <tr>
              <td colSpan={columns.length} className="px-3 py-8 text-center text-ink-3">
              {emptyMessage}
            </td>
          </tr>
        ) : (
          sortedRows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-border transition-colors hover:bg-surface-2">
              {columns.map((column) => (
                <td key={column.key} className="px-3 py-2 text-ink">
                  {renderCell(row, column)}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
