import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "outline";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual emphasis. `primary` owns primary actions only (The One Accent Rule). */
  variant?: ButtonVariant;
  /** Control size: sm/md/lg. */
  size?: ButtonSize;
  /** Shows a spinner and forces the disabled state while an action is in flight. */
  loading?: boolean;
  /** Optional leading icon placed before the label. */
  leftIcon?: ReactNode;
}

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors " +
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-0 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-contrast hover:bg-primary-deep focus-visible:ring-primary",
  secondary: "bg-secondary text-secondary-contrast hover:opacity-90 focus-visible:ring-secondary",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink focus-visible:ring-border-strong",
  outline: "border border-border text-ink hover:bg-surface-2 focus-visible:ring-border-strong",
};

const SIZES: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-3 py-1.5 text-sm",
  lg: "px-4 py-2 text-base",
};

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
      />
    </svg>
  );
}

/**
 * Primary interactive control for the platform. Four variants cover the action
 * hierarchy (primary action, featured/lucky, low-emphasis ghost, bordered
 * outline). Every variant ships default / hover / focus-visible / disabled /
 * loading states so affordances stay consistent across the product surface.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    leftIcon,
    className = "",
    children,
    disabled,
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <button
      ref={ref}
      type={rest.type ?? "button"}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={`${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading ? <Spinner /> : leftIcon}
      {children}
    </button>
  );
});

export default Button;
