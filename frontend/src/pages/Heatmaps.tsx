import { useEffect, useState } from "react";
import Button from "../components/Button";
import Card from "../components/Card";
import HeatmapChart from "../charts/HeatmapChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LongOperationStatus from "../components/LongOperationStatus";
import Skeleton from "../components/Skeleton";
import { useApi, abortable } from "../hooks/useApi";
import { useElapsedTime } from "../hooks/useElapsedTime";
import { computeGraph, getGraphSnapshots, getGraphValues } from "../services/graph";
import { useLotteryStore } from "../store/useLotteryStore";
import type { GraphSnapshotInfo } from "../types/graph";

const NO_LOTTERY_MESSAGE = "Selecciona una lotería para ver los mapas de calor de co-ocurrencia.";
const NO_DATA_MESSAGE =
  "No hay instantánea de co-ocurrencia para esta lotería. Haz clic en Calcular para generar una.";
const NO_PAIRS_MESSAGE = "No hay pares de co-ocurrencia en esta instantánea.";

function snapshotClass(selected: boolean): string {
  return `flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border px-3 py-2 text-left text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
    selected
      ? "border-primary bg-primary-soft text-primary-deep"
      : "border-border bg-surface text-ink-2 hover:bg-surface-2"
  }`;
}

/** Heatmaps page: compute + select co-occurrence snapshots → SVG heatmap grid. */
export default function Heatmaps() {
  const selectedLotteryCode = useLotteryStore((s) => s.selectedLotteryCode);
  const {
    data: snapshotList,
    isLoading: loadingList,
    error: listError,
    execute: fetchSnapshots,
  } = useApi(getGraphSnapshots);
  const {
    data: values,
    isLoading: loadingValues,
    error: valuesError,
    execute: fetchValues,
  } = useApi(getGraphValues);
  const {
    isLoading: computing,
    error: computeError,
    execute: compute,
    abort: abortCompute,
    isCancelled: computeCancelled,
  } = useApi(abortable((code: string, signal: AbortSignal) => computeGraph(code, "cooccurrence", signal)));
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const elapsed = useElapsedTime(computing);

  useEffect(() => {
    if (!selectedLotteryCode) return;
    setSelectedId(null);
    void fetchSnapshots(selectedLotteryCode, "cooccurrence");
  }, [selectedLotteryCode, fetchSnapshots]);

  useEffect(() => {
    if (selectedId !== null || !snapshotList) return;
    const latest = snapshotList.snapshots[0];
    if (latest) setSelectedId(latest.snapshot_id);
  }, [snapshotList, selectedId]);

  useEffect(() => {
    if (!selectedLotteryCode || selectedId === null) return;
    void fetchValues(selectedLotteryCode, selectedId);
  }, [selectedLotteryCode, selectedId, fetchValues]);

  const snapshots = snapshotList?.snapshots ?? [];
  const selected = snapshots.find((item) => item.snapshot_id === selectedId) ?? null;
  const cooccurrenceRows = values?.rows.filter((row) => row.metric_type === "cooccurrence") ?? [];
  const heatmapRows = cooccurrenceRows.map((row) => ({ subject: row.subject, value: row.value }));

  const handleCompute = async () => {
    if (!selectedLotteryCode || computing) return;
    await compute(selectedLotteryCode);
    setSelectedId(null);
    void fetchSnapshots(selectedLotteryCode, "cooccurrence");
  };

  const handleCancel = () => {
    if (!computing) return;
    abortCompute();
  };

  const renderVisualization = (code: string, item: GraphSnapshotInfo) => {
    if (valuesError)
      return (
        <ErrorState
          message={valuesError}
          onRetry={() => void fetchValues(code, item.snapshot_id)}
        />
      );
    if (loadingValues) return <Skeleton variant="card" />;
    if (cooccurrenceRows.length === 0) return <EmptyState message={NO_PAIRS_MESSAGE} />;
    return (
      <div className="space-y-4">
        <HeatmapChart rows={heatmapRows} />
        <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-3">
          <span>
             Sorteos <span className="font-medium text-ink">{item.draw_count}</span>
          </span>
          <span>
             Pares <span className="font-medium text-ink">{cooccurrenceRows.length}</span>
          </span>
        </p>
      </div>
    );
  };

  const renderContent = () => {
    if (!selectedLotteryCode) return <EmptyState message={NO_LOTTERY_MESSAGE} />;
    if (computeError)
      return <ErrorState message={computeError} onRetry={() => void handleCompute()} />;
    if (listError)
      return (
        <ErrorState
          message={listError}
          onRetry={() => void fetchSnapshots(selectedLotteryCode, "cooccurrence")}
        />
      );
    if (loadingList) return <Skeleton variant="card" />;
    if (computing || computeCancelled) {
      return (
        <LongOperationStatus
          elapsed={elapsed}
          onCancel={handleCancel}
          cancelled={computeCancelled && !computing}
          message="Calculando el mapa de calor; puede tardar varios minutos."
          responsibleNote="Recordá: los sorteos son aleatorios; ningún método mejora tus probabilidades."
        />
      );
    }
    if (snapshots.length === 0) {
      return (
        <EmptyState
          message={NO_DATA_MESSAGE}
          action={
            <Button
              variant="primary"
              onClick={() => void handleCompute()}
              disabled={computing}
              loading={computing}
            >
              Calcular
            </Button>
          }
        />
      );
    }
    return (
      <div className="space-y-5">
          <ul className="flex flex-col gap-2 sm:max-w-md" aria-label="Instantáneas de co-ocurrencia">
          {snapshots.map((item) => (
            <li key={item.snapshot_id}>
              <button
                type="button"
                aria-pressed={selectedId === item.snapshot_id}
                onClick={() => setSelectedId(item.snapshot_id)}
                className={snapshotClass(selectedId === item.snapshot_id)}
              >
                <span className="font-medium">#{item.snapshot_id}</span>
                <span>
                  v{item.version} · {item.draw_count} sorteos · {item.status} ·{" "}
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {selected ? renderVisualization(selectedLotteryCode, selected) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Heatmaps</h2>
          <p className="text-sm text-ink-3">
            Fuerza de co-ocurrencia entre pares de números para la lotería seleccionada.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => void handleCompute()}
          disabled={!selectedLotteryCode || computing}
          loading={computing}
        >
          Compute
        </Button>
      </div>
        <Card role="region" aria-label="Mapas de calor de co-ocurrencia">
        {renderContent()}
      </Card>
    </div>
  );
}
