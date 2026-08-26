import NavItem, { type NavItemDef } from "./NavItem";

interface NavGroupProps {
  /** Category title. */
  title: string;
  /** Navigation entries belonging to this group. */
  items: NavItemDef[];
  /** Render the group in icon-only mode (title and labels hidden). */
  collapsed?: boolean;
}

/**
 * Navigation group: a category title plus its list of nav items.
 * When collapsed only the items' icons remain visible.
 */
export default function NavGroup({ title, items, collapsed = false }: NavGroupProps) {
  return (
    <section aria-label={title} className="mb-4">
      <h2
        className={
          collapsed
            ? "sr-only"
            : "px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-ink-3"
        }
      >
        {title}
      </h2>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.to}>
            <NavItem {...item} showLabel={!collapsed} />
          </li>
        ))}
      </ul>
    </section>
  );
}
