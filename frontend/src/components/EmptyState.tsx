import type { ReactNode } from "react";

interface EmptyStateProps {
  message: string;
  action?: ReactNode;
}

/**
 * Reusable empty-state block shown when a successful response contains no data.
 * Optionally renders an action element (e.g. a generate button).
 */
export default function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div
      role="status"
      className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed border-gray-300 bg-gray-50 px-4 py-12 text-center"
    >
      <p className="text-sm text-gray-600">{message}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
