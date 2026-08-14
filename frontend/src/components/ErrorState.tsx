interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}

/**
 * Reusable error-state block for failed API requests. Renders the message in an
 * alert region and an optional retry button that re-executes the failed call.
 */
export default function ErrorState({
  message,
  onRetry,
  retryLabel = "Retry",
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-12 text-center"
    >
      <p className="text-sm font-medium text-red-700">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
