import Button from "./Button";
import Skeleton from "./Skeleton";
import { formatElapsed } from "../hooks/useElapsedTime";

interface LongOperationStatusProps {
  /** Elapsed seconds, updated by the page via useElapsedTime. */
  elapsed: number;
  /** Cancels the in-flight request. */
  onCancel: () => void;
  /** True once the user cancelled and we are back at the idle state. */
  cancelled: boolean;
  /** Main reassurance line, e.g. the existing Spanish compute message. */
  message: string;
  /** Brief responsible-play reminder shown near the action. */
  responsibleNote: string;
}

/**
 * Shared waiting UI for long, non-incremental backend computes. There is NO
 * fake progress bar (the backend answers once after minutes); instead the user
 * can cancel, sees elapsed time, and keeps the responsible-play reminder. The
 * elapsed readout uses aria-live="polite" so screen readers get periodic
 * updates without interrupting.
 */
export default function LongOperationStatus({
  elapsed,
  onCancel,
  cancelled,
  message,
  responsibleNote,
}: LongOperationStatusProps) {
  if (cancelled) {
    return (
      <p className="text-sm text-ink-2" role="status">
        Cancelado. Podés volver a intentarlo cuando quieras.
      </p>
    );
  }

  return (
    <div aria-busy="true" className="space-y-3">
      <p aria-live="polite" className="text-sm text-ink-2">
        {message}
      </p>
      <p aria-live="polite" className="text-sm tabular-nums text-ink-2">
        Tiempo transcurrido: {formatElapsed(elapsed)}
      </p>
      <p className="text-sm text-ink-3">{responsibleNote}</p>
      <Skeleton variant="card" />
      <Button variant="outline" onClick={onCancel}>
        Cancelar
      </Button>
    </div>
  );
}
