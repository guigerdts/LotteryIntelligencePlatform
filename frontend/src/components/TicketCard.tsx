import type { HTMLAttributes } from "react";

export interface TicketCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Lottery name shown in the stub header. */
  lotteryName: string;
  /** Combination numbers rendered as bold circular chips. */
  numbers: number[];
  /** 1-based position; rank === 1 receives the sparing Fortune Gold "lucky" highlight. */
  rank?: number;
  /** Optional small caption (e.g. super number + coverage weight). */
  meta?: string;
}

/**
 * Generated-combination presentation that reads as a lottery ticket rather than
 * a data table: a warm-paper stub with a brand dot, a dashed perforation
 * separating the header from the numbers body, and bold primary-soft number
 * chips. The top-ranked ticket earns the single Fortune Gold accent (ring +
 * star) — gold is reserved for this rare featured moment (The One Accent Rule).
 * Visual only; no text labels or copy are introduced here.
 */
export default function TicketCard({
  lotteryName,
  numbers,
  rank,
  meta,
  className = "",
  ...rest
}: TicketCardProps) {
  const isLucky = rank === 1;
  return (
    <div
      className={[
        "bg-surface border rounded-lg shadow-sm transition-shadow hover:shadow-md",
        isLucky ? "border-secondary ring-1 ring-secondary" : "border-border",
        className,
      ].join(" ")}
      {...rest}
    >
      <div className="rounded-t-lg bg-canvas p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full bg-primary" />
            <span className="truncate text-sm font-semibold text-ink">{lotteryName}</span>
          </div>
          {isLucky ? (
            <span
              aria-label="Featured combination"
              className="inline-flex shrink-0 items-center rounded-full bg-secondary-soft px-2 py-0.5"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="h-3 w-3 text-secondary">
                <path d="M10 1.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L10 15l-5.3 2.6 1-5.8L1.5 7.7l5.9-.9L10 1.5z" />
              </svg>
            </span>
          ) : null}
        </div>
      </div>

      <div aria-hidden="true" className="border-t border-dashed border-border" />

      <div className="rounded-b-lg bg-canvas p-4">
        <ul aria-label="Combination numbers" className="flex flex-wrap gap-2">
          {numbers.map((n, i) => (
            <li
              key={i}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary-soft text-sm font-semibold text-primary-deep"
            >
              {n}
            </li>
          ))}
        </ul>
        {meta ? <p className="mt-3 text-xs text-ink-2">{meta}</p> : null}
      </div>
    </div>
  );
}
