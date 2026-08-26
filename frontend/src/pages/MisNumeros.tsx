import { useState } from "react";
import Button from "../components/Button";
import Card from "../components/Card";
import TicketCard from "../components/TicketCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LongOperationStatus from "../components/LongOperationStatus";
import TierTable from "../components/TierTable";
import { useApi, abortable } from "../hooks/useApi";
import { useElapsedTime } from "../hooks/useElapsedTime";
import { AppError } from "../services/api";
import { runNumbersPipeline } from "../services/pipeline";
import { useLotteryStore } from "../store/useLotteryStore";
import type { GenerationResult } from "../types/gen";
import type { PipelineRunResult, PipelineStageResult } from "../types/pipeline";

const NO_LOTTERY_MESSAGE = "Selecciona una lotería para generar tus números.";
const IDLE_HINT = "Haz clic en Generar números para ejecutar la cadena de análisis completa y armar tu boleto.";
/** Owner decision: every ticket is valid for BOTH draws; no toggle exists. */
const DUAL_DRAW_LABEL = "Un boleto, dos sorteos (Baloto + Revancha)";
const DISCLAIMER_TEXT =
  "Los números se generan a partir de la frecuencia histórica (F5) y un refuerzo de números fríos para mejorar la cobertura. Los sorteos oficiales son completamente aleatorios: ningún método mejora la probabilidad de acierto y ningún resultado está garantizado.";
/** Default combination count sent in the payload (R4/D11). */
const DEFAULT_COUNT = 5;
const FIELD_CLASS =
  "block w-full rounded-md border border-border px-3 py-2 text-sm text-ink focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:bg-surface-2";

/** Map a backend pipeline error to a user-friendly message. */
function mapPipelineError(err: unknown): string {
  if (err instanceof AppError && err.code === "PIPE_STAGE_FAILED") {
    return `La cadena se detuvo en una etapa fallida: ${err.message}`;
  }
  return err instanceof Error ? err.message : "Error desconocido";
}

/** Map a pipeline stage error code to a friendly, screen-reader-first summary. */
const STAGE_ERROR_FRIENDLY: Record<string, string> = {
  PIPE_STAGE_FAILED: "La etapa del pipeline falló durante el análisis.",
};

function stageErrorMessage(stage: PipelineStageResult): string {
  return (
    STAGE_ERROR_FRIENDLY[stage.error_code ?? ""] ?? stage.detail ?? "La etapa falló."
  );
}

/** Wrapped orchestrator call that surfaces mapped messages to the useApi hook. */
async function runWithMessages(
  params: { lottery_id: number; count?: number },
  signal: AbortSignal
): Promise<PipelineRunResult> {
  try {
    return await runNumbersPipeline(
      { lottery_id: params.lottery_id, count: params.count },
      signal
    );
  } catch (err) {
    throw new Error(mapPipelineError(err));
  }
}

const STAGE_STATUS_LABEL: Record<string, string> = {
  failed: "fallido",
  skipped: "omitido",
  running: "en curso",
};

/** Ordered per-stage report rendered straight from the response (R2). */
function StageReport({ stages }: { stages: PipelineStageResult[] }) {
  return (
    <ol aria-label="Etapas del pipeline" className="space-y-1 text-sm">
      {stages.map((stage) => (
        <li
          key={stage.name}
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-border px-3 py-1.5"
        >
          <span className="font-mono text-xs font-medium text-ink">{stage.name}</span>
          <span
            data-status={stage.status}
            className={
              stage.status === "failed"
                ? "text-xs font-semibold text-error"
                : stage.status === "skipped"
                  ? "text-xs text-ink-3"
                  : "text-xs font-semibold text-success"
            }
          >
            {STAGE_STATUS_LABEL[stage.status] ?? stage.status}
          </span>
          <span className="text-xs text-ink-3">{stage.detail}</span>
          {stage.status === "failed" ? (
            <span role="alert" className="w-full text-xs text-error">
              {stageErrorMessage(stage)}
              {stage.error_code ? (
                <span aria-hidden="true" className="ml-1 font-mono opacity-80">
                  ({stage.error_code})
                </span>
              ) : null}
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

/** Ticket presentation: dual-draw label plus a responsive grid of TicketCards. */
function TicketCards({
  result,
  lotteryName,
}: {
  result: GenerationResult;
  lotteryName: string;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm font-semibold text-ink">{DUAL_DRAW_LABEL}</p>
      <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-3">
        <span>
          Instantánea <span className="font-medium text-ink">#{result.snapshot_id}</span>
        </span>
        <span>
          Semilla <span className="font-medium text-ink">{result.seed}</span>
        </span>
        <span>
          Huella <span className="font-mono text-xs text-ink">{result.fingerprint}</span>
        </span>
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {result.combinations.map((row) => {
          const metaParts: string[] = [];
          if (row.super_number != null) metaParts.push(`Super ${row.super_number}`);
          if (row.score != null) metaParts.push(`Peso ${row.score.toFixed(2)}`);
          return (
            <TicketCard
              key={row.position}
              lotteryName={lotteryName}
              numbers={row.numbers}
              rank={row.position}
              meta={metaParts.join(" · ") || undefined}
            />
          );
        })}
      </div>
    </div>
  );
}

/**
 * Mis Números page. One CTA runs the whole POST /pipeline/numbers chain; the
 * busy state holds for the entire minutes-scale request and the result renders
 * straight from the response — nothing is refetched afterwards.
 */
export default function MisNumeros() {
  const selectedLotteryId = useLotteryStore((s) => s.selectedLotteryId);
  const lotteryName = useLotteryStore(
    (s) => s.lotteries.find((l) => l.id === s.selectedLotteryId)?.name ?? "",
  );
  const [countInput, setCountInput] = useState(String(DEFAULT_COUNT));
  const { data, isLoading, error, execute, abort, isCancelled } = useApi(
    abortable(runWithMessages)
  );

  const running = isLoading;
  const elapsed = useElapsedTime(running);

  const runPipeline = () => {
    if (!selectedLotteryId || running) return;
    void execute({ lottery_id: selectedLotteryId, count: Number(countInput) });
  };

  const handleCancel = () => {
    if (!running) return;
    abort();
  };

  const renderContent = () => {
    if (!selectedLotteryId) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return <ErrorState message={error} onRetry={runPipeline} />;
    }
    if (running || isCancelled) {
      return (
        <LongOperationStatus
          elapsed={elapsed}
          onCancel={handleCancel}
          cancelled={isCancelled && !running}
          message="Ejecutando la cadena de análisis completa; puede tardar varios minutos."
          responsibleNote="Recordá: los sorteos son aleatorios; ningún método mejora tus probabilidades."
        />
      );
    }
    if (data) {
      return (
        <div className="space-y-4">
          <StageReport stages={data.stages} />
          {data.result ? (
            <TicketCards result={data.result} lotteryName={lotteryName} />
          ) : (
            <p className="text-sm text-error">
              La cadena se detuvo antes de generar combinaciones.
            </p>
          )}
        </div>
      );
    }
    return <p className="text-sm text-ink-3">{IDLE_HINT}</p>;
  };

  return (
    <div className="space-y-6 p-4 sm:p-6 max-sm:pb-28">
      <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-ink">Mis Números</h2>
        <p className="text-sm text-ink-3">
          Una solicitud calcula la frecuencia histórica (estadísticas + probabilidad F5) y genera
          combinaciones con cobertura reforzada para el sorteo seleccionado.
        </p>
      </div>
      <Button
        variant="primary"
        onClick={runPipeline}
        disabled={!selectedLotteryId || running}
        loading={running}
        className="max-sm:hidden"
      >
        Generar números
      </Button>
      </div>

      <Card aria-label="Cantidad de combinaciones" className="hidden sm:block">
          <label htmlFor="mis-numeros-count" className="mb-1 block text-sm font-medium text-ink-2">
            Cantidad
          </label>
        <input
          id="mis-numeros-count"
          type="number"
          min={1}
          max={100}
          value={countInput}
          onChange={(event) => setCountInput(event.target.value)}
          disabled={!selectedLotteryId || running}
          className={`${FIELD_CLASS} max-w-[8rem]`}
        />
      </Card>

      <Card role="region" aria-label="Resultados de Mis números">
        {renderContent()}
      </Card>

      <Card role="region" aria-label="Referencia de categorías de premios oficiales">
        <TierTable />
      </Card>

      <Card role="region" aria-label="Cómo se generan los números">
        <h3 className="mb-2 text-sm font-semibold text-ink">Transparencia del generador</h3>
        <ul className="space-y-1 text-sm text-ink-2">
          <li>
            <span className="font-medium text-ink">Frecuencia histórica (F5):</span> cada número se
            pondera según cuánto ha salido, normalizado sobre el universo del juego.
          </li>
          <li>
            <span className="font-medium text-ink">Refuerzo de números fríos:</span> los números
            sub-representados reciben un peso mayor para ampliar la cobertura.
          </li>
          <li>
            <span className="font-medium text-ink">Ventaja esperada (EV):</span> el generador optimiza
            la cobertura y el reparto del premio si ganas, pero la probabilidad de acierto es la del
            juego (1 entre C) y no cambia.
          </li>
        </ul>
      </Card>

      <footer className="rounded-md border border-warning/40 bg-warning-soft p-4">
        <p className="text-sm text-ink">{DISCLAIMER_TEXT}</p>
      </footer>

      {/* Mobile-only sticky action bar: keeps the Generate CTA and count input
          reachable while scrolling the long page. Hidden on desktop so the
          header CTA + Cantidad card above stay the source of truth there. */}
      <div className="max-sm:sticky max-sm:bottom-0 max-sm:z-10 max-sm:mt-6 max-sm:bg-canvas/95 max-sm:backdrop-blur max-sm:border-t max-sm:border-border max-sm:px-4 max-sm:py-3 max-sm:pb-[calc(0.75rem+env(safe-area-inset-bottom))] sm:hidden">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label
              htmlFor="mn-count-mobile"
              className="mb-1 block text-sm font-medium text-ink-2"
            >
              Cantidad de combinaciones
            </label>
            <input
              id="mn-count-mobile"
              type="number"
              min={1}
              max={100}
              value={countInput}
              onChange={(event) => setCountInput(event.target.value)}
              disabled={!selectedLotteryId || running}
              className={`${FIELD_CLASS} max-w-[8rem]`}
            />
          </div>
          {running ? (
            <Button variant="outline" onClick={handleCancel}>
              Cancelar
            </Button>
          ) : (
            <Button variant="primary" onClick={runPipeline} disabled={!selectedLotteryId}>
              Generar
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
