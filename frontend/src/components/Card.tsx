import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Inner spacing; defaults to `md` (16px) to match the previous `p-4` cards. */
  padding?: "none" | "sm" | "md" | "lg";
  /** Adds a hover elevation transition for clickable / selectable cards. */
  interactive?: boolean;
}

const PADDING: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

/**
 * Surface container with the canonical warm-paper tint, hairline border and
 * soft shadow. Renders a `div`; pass `role`/`aria-*` (e.g. `role="region"` with
 * an `aria-label`) when it must act as a labelled landmark.
 */
export function Card({
  padding = "md",
  interactive = false,
  className = "",
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={`bg-surface border border-border rounded-md shadow-sm ${
        interactive ? "transition-shadow hover:shadow-md" : ""
      } ${PADDING[padding]} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

/** Optional header block: title row above a card body. */
export function CardHeader({ className = "", children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`mb-3 ${className}`} {...rest}>
      {children}
    </div>
  );
}

/** Optional body wrapper for card content. */
export function CardBody({ className = "", children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={className} {...rest}>
      {children}
    </div>
  );
}

export default Card;
