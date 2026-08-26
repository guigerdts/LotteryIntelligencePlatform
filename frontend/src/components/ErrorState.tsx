interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

/**
 * Reusable error-state block for failed API requests. Renders the message in an
 * alert region and an optional retry button that re-executes the failed call.
 */
export default function ErrorState({ message, onRetry,   retryLabel = "Reintentar" }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-md border border-error/30 bg-error-soft px-4 py-12 text-center"
    >
      <p className="text-sm font-medium text-error">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-error/40 bg-surface px-3 py-1.5 text-sm font-medium text-error hover:bg-error-soft focus:outline-none focus-visible:ring-2 focus-visible:ring-error"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
