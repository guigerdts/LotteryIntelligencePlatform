import EmptyState from "./EmptyState";

interface ComingSoonProps {
  title: string;
}

/**
 * Reusable placeholder page for routes whose module is not implemented yet.
 * Renders the page heading plus an empty-state "coming soon" message without
 * making any API calls.
 */
export default function ComingSoon({ title }: ComingSoonProps) {
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <EmptyState message={`Próximamente — ${title} disponible en una futura fase.`} />
    </div>
  );
}
