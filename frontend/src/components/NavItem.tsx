import { NavLink } from "react-router-dom";

/** Definition of a single navigation entry. */
export interface NavItemDef {
  /** Visible label. */
  label: string;
  /** Route path. */
  to: string;
  /** Match the route exactly instead of by prefix (root path). */
  end?: boolean;
}

interface NavItemProps extends NavItemDef {
  /** Hide the text label, keeping it in the accessibility tree. */
  showLabel?: boolean;
}

/**
 * Single navigation entry rendered as a router link. Active styling is
 * derived from the current route via NavLink and exposed with
 * aria-current="page".
 */
export default function NavItem({ label, to, end, showLabel = true }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          "flex items-center gap-3 rounded-md border-l-2 border-transparent px-3 py-2 text-sm font-medium transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary",
          isActive
            ? "border-primary bg-surface-2 text-ink"
            : "text-ink-2 hover:bg-surface-2 hover:text-ink",
        ].join(" ")
      }
    >
      <span aria-hidden="true" className="flex h-4 w-4 shrink-0 items-center justify-center">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
          <circle cx="10" cy="10" r="4" />
        </svg>
      </span>
      <span className={showLabel ? "whitespace-nowrap" : "sr-only"}>{label}</span>
    </NavLink>
  );
}
