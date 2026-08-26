import { useEffect, useMemo, type ReactNode } from "react";
import Card from "../components/Card";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getDraws } from "../services/draws";
import { getFrequencies } from "../services/statistics";
import { getSystemInfo } from "../services/system";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Draw } from "../types/draw";
import type { FrequencyRow } from "../types/statistics";

const LATEST_DRAWS = 5;
const TOP_FREQUENCIES = 5;
const NO_LOTTERY_MESSAGE = "Selecciona una lotería para ver su resumen operativo.";
const NO_DATA_MESSAGE = "No hay datos disponibles para esta lotería.";

const drawColumns: DataColumn<Draw>[] = [
  { key: "draw_number", label: "Sorteo", sortable: true },
  { key: "draw_date", label: "Fecha", sortable: true },
  {
    key: "numbers",
    label: "Números",
    render: (row) => row.numbers.map((n) => n.number).join(" - "),
  },
  { key: "super_number", label: "Super", render: (row) => row.super_number ?? "—" },
];

/** Sort frequency rows and keep the top N most (desc) or least (asc) frequent. */
function topFrequencies(rows: FrequencyRow[], direction: "desc" | "asc") {
  return [...rows]
    .sort((a, b) => (direction === "desc" ? b.count - a.count : a.count - b.count))
    .slice(0, TOP_FREQUENCIES);
}

function FrequencyList({ title, rows }: { title: string; rows: FrequencyRow[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{title}</h4>
      <ol className="space-y-1">
        {rows.map((row, index) => (
          <li
            key={row.number}
            className="flex items-center justify-between rounded px-2 py-1 text-sm odd:bg-surface-2"
          >
            <span className="w-6 text-ink-2">{index + 1}</span>
            <span className="font-medium text-ink">{row.number}</span>
            <span className="text-ink-2">{row.count}×</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <Card role="region" aria-labelledby={id}>
      <h3 id={id} className="mb-3 text-sm font-semibold text-ink">
        {title}
      </h3>
      {children}
    </Card>
  );
}

/**
 * Landing/operational summary page (Inicio). Shows the latest draws, a compact
 * frequency snapshot (top-5 most/least frequent numbers) and a secondary API
 * health/version block for the globally selected lottery.
 */
export default function Home() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: drawRows,
    isLoading: drawsLoading,
    error: drawsError,
    execute: fetchDraws,
  } = useApi(getDraws);
  const {
    data: freqData,
    isLoading: freqLoading,
    error: freqError,
    execute: fetchFrequencies,
  } = useApi(getFrequencies);
  const {
    data: systemData,
    isLoading: systemLoading,
    error: systemError,
    execute: fetchSystem,
  } = useApi(getSystemInfo);

  useEffect(() => {
    if (selectedLotteryCode) {
      void fetchDraws(selectedLotteryCode, 1, LATEST_DRAWS);
      void fetchFrequencies(selectedLotteryCode);
    }
    void fetchSystem();
  }, [selectedLotteryCode, fetchDraws, fetchFrequencies, fetchSystem]);

  const drawList = drawRows ?? [];
  const [mostFrequent, leastFrequent] = useMemo(() => {
    const rows = freqData?.frequencies ?? [];
    return [topFrequencies(rows, "desc"), topFrequencies(rows, "asc")];
  }, [freqData]);

  const renderDraws = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (drawsError) {
      return (
        <ErrorState
          message={drawsError}
          onRetry={() => void fetchDraws(selectedLotteryCode, 1, LATEST_DRAWS)}
        />
      );
    }
    if (drawList.length === 0 && !drawsLoading) return <EmptyState message={NO_DATA_MESSAGE} />;
    return (
      <DataTable
        columns={drawColumns}
        rows={drawList}
        rowKey={(row) => String(row.id)}
        caption="Últimos sorteos"
        loading={drawsLoading}
        loadingRows={LATEST_DRAWS}
      />
    );
  };

  const renderFrequencies = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (freqError) {
      return (
        <ErrorState
          message={freqError}
          onRetry={() => void fetchFrequencies(selectedLotteryCode)}
        />
      );
    }
    if (freqLoading) {
      return (
        <div className="space-y-3" aria-hidden="true">
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </div>
      );
    }
    if (mostFrequent.length === 0) return <EmptyState message={NO_DATA_MESSAGE} />;
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <FrequencyList title="Más frecuentes" rows={mostFrequent} />
        <FrequencyList title="Menos frecuentes" rows={leastFrequent} />
      </div>
    );
  };

  const renderSystem = () => {
    if (systemError) return <ErrorState message={systemError} onRetry={() => void fetchSystem()} />;
    if (systemLoading || !systemData) return <Skeleton variant="text" className="max-w-xs" />;
    const { health, version } = systemData;
    return (
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="flex items-center gap-2">
          <dt className="text-ink-2">Estado de la API</dt>
          <dd className="flex items-center gap-1.5 font-medium text-ink">
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${health.status === "ok" ? "bg-success" : "bg-warning"}`}
            />
            {health.status}
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="text-ink-2">Versión</dt>
          <dd className="font-medium text-ink">{version.version}</dd>
        </div>
      </dl>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="border-l-4 border-primary pl-3">
        <h2 className="text-lg font-semibold text-ink">Resumen operativo</h2>
        <p className="text-sm text-ink-3">
          Últimos sorteos, instantánea de frecuencias y estado de la API para la lotería seleccionada.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section id="home-draws-title" title="Últimos sorteos">
          {renderDraws()}
        </Section>
        <Section id="home-frequency-title" title="Resumen de frecuencias">
          {renderFrequencies()}
        </Section>
      </div>

      <Section id="home-system-title" title="Sistema">
        {renderSystem()}
      </Section>
    </div>
  );
}
