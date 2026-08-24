type SkeletonVariant = "text" | "row" | "card";

interface SkeletonProps {
  variant?: SkeletonVariant;
  className?: string;
}

const VARIANT_CLASSES: Record<SkeletonVariant, string> = {
  text: "h-4 w-full rounded",
  row: "h-10 w-full rounded",
  card: "h-40 w-full rounded-md border border-gray-200",
};

/**
 * Reusable loading placeholder hidden from the accessibility tree. Variants map
 * to common page layouts: text lines, table rows, and card blocks.
 */
export default function Skeleton({ variant = "text", className = "" }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse bg-gray-200 ${VARIANT_CLASSES[variant]} ${className}`}
    />
  );
}
