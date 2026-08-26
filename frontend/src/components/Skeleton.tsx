type SkeletonVariant = "text" | "card";

interface SkeletonProps {
  variant?: SkeletonVariant;
  className?: string;
}

const VARIANT_CLASSES: Record<SkeletonVariant, string> = {
  text: "h-4 w-full rounded",
  card: "h-40 w-full rounded-md border border-border",
};

/**
 * Reusable loading placeholder hidden from the accessibility tree. Variants map
 * to common page layouts: text lines and card blocks.
 */
export default function Skeleton({ variant = "text", className = "" }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse bg-surface-2 ${VARIANT_CLASSES[variant]} ${className}`}
    />
  );
}
