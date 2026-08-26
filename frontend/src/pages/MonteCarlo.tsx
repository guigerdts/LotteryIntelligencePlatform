import { useEffect, useState } from "react";
import Button from "../components/Button";
import Card from "../components/Card";
import DistributionChart from "../charts/DistributionChart";
import DataTable, { type DataColumn } from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LongOperationStatus from "../components/LongOperationStatus";
import Skeleton from "../components/Skeleton";
import { useApi, abortable } from "../hooks/useApi";
import { useElapsedTime } from "../hooks/useElapsedTime";
import { generateProbability, getProbabilities } from "../services/probability";
import { useLotteryStore } from "../store/useLotteryStore";
import type { ProbabilitySnapshot, ProbRow } from "../types/probability";

const NO_LOTTERY_MESSAGE = "Selecciona una lotería para ver las filas de probabilidad.";
const NO_DATA_MESSAGE =
  "No hay probabilidades disponibles para esta lotería. Haz clic en Generar para calcularlas.";

const probabilityColumns: DataColumn<ProbRow>[] = [
  { key: "model_id", label: "Modelo", sortable: true },
  { key: "subject", label: "Sujeto", sortable: true },
  { key: "draw_number", label: "Sorteo", sortable: true },
  { key: "value", label: "Probabilidad", sortable: true },
];

function SnapshotSummary({ snapshot }: { snapshot: ProbabilitySnapshot }) {
  return (
    <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-3">
      <span>
        Instantánea <span className="font-medium text-ink">#{snapshot.snapshot_id}</span>
      </span>
      <span>
        Rango{" "}
        <span className="font-medium text-ink">
          {snapshot.draws_from}–{snapshot.draws_to}
        </span>
      </span>
      <span>
        Sorteos <span className="font-medium text-ink">{snapshot.draw_count}</span>
      </span>
      <span>
        Modelos <span className="font-medium text-ink">{snapshot.model_set}</span>
      </span>
    </p>
  );
}

/**
 * Monte Carlo page (Avanzado). Triggers probability generation via
 * POST /probability/generate and renders the resulting probability rows from
 * GET /probability/{code}/probabilities as a table with a distribution chart.
 */
export default function MonteCarlo() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: list,
    isLoading: loading,
    error,
    execute: fetchProbabilities,
  } = useApi(getProbabilities);
  const {
    isLoading: generating,
    error: generateError,
    execute: generate,
    abort: abortGenerate,
    isCancelled: generateCancelled,
  } = useApi(abortable((code: string, signal: AbortSignal) => generateProbability(code, "incremental", signal)));
  const [snapshot, setSnapshot] = useState<ProbabilitySnapshot | null>(null);
  const elapsed = useElapsedTime(generating);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    setSnapshot(null);
    void fetchProbabilities(selectedLotteryCode);
  }, [selectedLotteryCode, fetchProbabilities]);

  const handleGenerate = async () => {
    if (!selectedLotteryCode || generating) return;
    const result = await generate(selectedLotteryCode);
    if (result) setSnapshot(result);
    void fetchProbabilities(selectedLotteryCode);
  };

  const handleCancel = () => {
    if (!generating) return;
    abortGenerate();
  };

  const renderContent = () => {
    if (!selectedLotteryCode) {
      return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    }
    if (error) {
      return (
        <ErrorState message={error} onRetry={() => void fetchProbabilities(selectedLotteryCode)} />
      );
    }
    if (loading) {
      return <Skeleton variant="card" />;
    }
    if (generating || generateCancelled) {
      return (
        <LongOperationStatus
          elapsed={elapsed}
          onCancel={handleCancel}
          cancelled={generateCancelled && !generating}
          message="Ejecutando la simulación de Monte Carlo; puede tardar varios minutos."
          responsibleNote="Recordá: los sorteos son aleatorios; ningún método mejora tus probabilidades."
        />
      );
    }
    if (generateError) {
      return <ErrorState message={generateError} onRetry={() => void handleGenerate()} />;
    }
    const rows = list?.probabilities ?? [];
    if (rows.length === 0) {
      return (
        <EmptyState
          message={NO_DATA_MESSAGE}
          action={
            <Button
              variant="primary"
              onClick={() => void handleGenerate()}
              disabled={generating}
              loading={generating}
            >
              Generar
            </Button>
          }
        />
      );
    }
    return (
      <div className="space-y-4">
        {snapshot ? <SnapshotSummary snapshot={snapshot} /> : null}
        <DataTable
          columns={probabilityColumns}
          rows={rows}
          rowKey={(row) => `${row.model_id}-${row.subject}-${row.draw_number}`}
          caption="Filas de probabilidad"
        />
        <DistributionChart rows={rows.map((row) => ({ subject: row.subject, value: row.value }))} />
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Monte Carlo</h2>
          <p className="text-sm text-ink-3">          Filas de probabilidad para la lotería seleccionada.</p>
        </div>
        <Button
          variant="primary"
          onClick={() => void handleGenerate()}
          disabled={!selectedLotteryCode || generating}
          loading={generating}
        >
          Generate
        </Button>
      </div>
        <Card role="region" aria-label="Resultados de probabilidad">
        {renderContent()}
      </Card>
    </div>
  );
}
