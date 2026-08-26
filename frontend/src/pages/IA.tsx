import { useEffect, useMemo, type ReactNode } from "react";
import AssistantPanel from "../components/AssistantPanel";
import Card from "../components/Card";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Skeleton from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { getMetrics, getModels } from "../services/ml";
import { getProbabilities } from "../services/probability";
import { getSystemInfo } from "../services/system";
import { useLotteryStore } from "../store/useLotteryStore";
import type { MLSnapshot } from "../types/ml";
import type { ProbRow } from "../types/probability";

const RECENT_ROWS = 5;
const TOP_METRICS = 3;
const NO_LOTTERY_MESSAGE = "Selecciona una lotería para ver el estado del asistente IA.";
const NO_MODELS_MESSAGE = "Aún no hay modelos de ML entrenados para esta lotería.";
const NO_METRICS_MESSAGE = "No hay métricas del modelo disponibles para esta lotería.";
const NO_PROBABILITY_MESSAGE = "Aún no hay filas de probabilidad disponibles para esta lotería.";

const probabilityColumns: DataColumn<ProbRow>[] = [
  { key: "model_id", label: "Modelo", sortable: true },
  { key: "subject", label: "Sujeto", sortable: true },
  { key: "draw_number", label: "Sorteo", sortable: true },
  { key: "value", label: "Probabilidad", sortable: true, sortValue: (row) => Number(row.value) },
];

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

function SnapshotSummary({ snapshot }: { snapshot: MLSnapshot }) {
  const checksum =
    snapshot.checksum.length > 8 ? `${snapshot.checksum.slice(0, 8)}…` : snapshot.checksum;
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-3">
      <span>
        Conjunto de modelos <span className="font-medium text-ink">{snapshot.model_set}</span>
      </span>
      <span>
        Versión <span className="font-medium text-ink">{snapshot.version}</span>
      </span>
      <span>
        Estado <span className="font-medium text-ink">{snapshot.status}</span>
      </span>
      <span>
        Suma de verificación <span className="font-mono text-xs text-ink">{checksum}</span>
      </span>
    </p>
  );
}

/**
 * IA page (AI Assistant). No AI engine exists — this page composes existing
 * endpoints (system health/version, active ML snapshot + top metrics, latest
 * probability rows) into a real intelligence status view. Each section owns its
 * loading/error/empty state (R20) and renders independently as it resolves.
 */
export default function IA() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: systemData,
    isLoading: systemLoading,
    error: systemError,
    execute: fetchSystem,
  } = useApi(getSystemInfo);
  const {
    data: snapshot,
    isLoading: modelsLoading,
    error: modelsError,
    execute: fetchModels,
  } = useApi(getModels);
  const {
    data: metrics,
    isLoading: metricsLoading,
    error: metricsError,
    execute: fetchMetrics,
  } = useApi(getMetrics);
  const {
    data: probabilityList,
    isLoading: probLoading,
    error: probError,
    execute: fetchProbabilities,
  } = useApi(getProbabilities);

  useEffect(() => {
    void fetchSystem();
  }, [fetchSystem]);

  useEffect(() => {
    if (!selectedLotteryId) return;
    void fetchModels(selectedLotteryId);
    void fetchMetrics(selectedLotteryId);
  }, [selectedLotteryId, fetchModels, fetchMetrics]);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    void fetchProbabilities(selectedLotteryCode, { last: RECENT_ROWS });
  }, [selectedLotteryCode, fetchProbabilities]);

  const topMetrics = useMemo(
    () =>
      (metrics ?? [])
        .slice()
        .sort((a, b) => b.value - a.value)
        .slice(0, TOP_METRICS),
    [metrics]
  );

  const renderSystem = () => {
    if (systemError) {
      return <ErrorState message={systemError} onRetry={() => void fetchSystem()} />;
    }
    if (systemLoading || !systemData) {
      return <Skeleton variant="text" className="max-w-xs" />;
    }
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

  const renderModel = () => {
    if (!selectedLotteryId) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    const error = modelsError ?? metricsError;
    if (error) {
      return (
        <ErrorState
          message={error}
          onRetry={() => {
            void fetchModels(selectedLotteryId);
            void fetchMetrics(selectedLotteryId);
          }}
        />
      );
    }
    if (modelsLoading || metricsLoading) return <Skeleton variant="card" />;
    if (!snapshot && topMetrics.length === 0) return <EmptyState message={NO_MODELS_MESSAGE} />;
    return (
      <div className="space-y-3">
        {snapshot ? <SnapshotSummary snapshot={snapshot} /> : null}
        {topMetrics.length === 0 ? (
          <p className="text-sm text-ink-3">{NO_METRICS_MESSAGE}</p>
        ) : (
          <ol className="space-y-1">
            {topMetrics.map((row) => (
              <li
                key={`${row.model_id}-${row.number}-${row.metric_name}`}
                className="flex items-center justify-between rounded px-2 py-1 text-sm odd:bg-surface-2"
              >
                <span className="font-medium text-ink">{row.model_id}</span>
                <span className="text-ink-2">{row.metric_name}</span>
                <span className="text-ink">{row.value.toFixed(4)}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    );
  };

  const renderProbabilities = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (probError) {
      return (
        <ErrorState
          message={probError}
          onRetry={() => void fetchProbabilities(selectedLotteryCode, { last: RECENT_ROWS })}
        />
      );
    }
    if (probLoading) return <Skeleton variant="card" />;
    const rows = probabilityList?.probabilities ?? [];
    if (rows.length === 0) return <EmptyState message={NO_PROBABILITY_MESSAGE} />;
    return (
      <DataTable
        columns={probabilityColumns}
        rows={rows}
        rowKey={(row) => `${row.model_id}-${row.subject}-${row.draw_number}`}
        caption="Filas de probabilidad recientes"
      />
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-ink">Asistente IA</h2>
        <p className="text-sm text-ink-3">
          Estado de inteligencia derivado del sistema en vivo, el modelo de ML activo y las últimas
          filas de probabilidad para la lotería seleccionada.
        </p>
      </div>
      <Section id="ia-system-title" title="Estado del sistema">
        {renderSystem()}
      </Section>
      <Section id="ia-model-title" title="Estado del modelo">
        {renderModel()}
      </Section>
      <Section id="ia-probability-title" title="Probabilidades recientes">
        {renderProbabilities()}
      </Section>
      <AssistantPanel lotteryCode={selectedLotteryCode} />
    </div>
  );
}
