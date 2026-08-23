import { useEffect } from "react";
import { useModuleStore } from "../store/useModuleStore";
import NavGroup from "./NavGroup";
import type { NavItemDef } from "./NavItem";

interface NavGroupDef {
  title: string;
  items: NavItemDef[];
}

/** Navigation structure: five categories following the design Navigation table. */
const NAV_GROUPS: NavGroupDef[] = [
  {
    title: "General",
    items: [
      { label: "Inicio", to: "/", end: true },
      { label: "Historial", to: "/historial" },
    ],
  },
  {
    title: "Análisis",
    items: [
      { label: "Estadísticas", to: "/estadisticas" },
      { label: "Heatmaps", to: "/heatmaps" },
      { label: "Tendencias", to: "/tendencias" },
    ],
  },
  {
    title: "Avanzado",
    items: [
      { label: "Monte Carlo", to: "/monte-carlo" },
      { label: "Redes", to: "/redes" },
      { label: "IA", to: "/ia" },
    ],
  },
  {
    title: "ML",
    items: [
      { label: "Modelos", to: "/modelos" },
      { label: "Experimentos", to: "/experimentos" },
      { label: "Backtesting", to: "/backtesting" },
      { label: "Deep Learning", to: "/dl" },
    ],
  },
  {
    title: "Generador",
    items: [{ label: "Generador", to: "/generador" }],
  },
];

const MOBILE_QUERY = "(max-width: 767px)";

/**
 * Persistent grouped navigation rail. Collapse state comes from the global
 * module store: when collapsed only icons remain visible and labels stay in
 * the accessibility tree via sr-only. On mobile viewports (< md) the rail
 * collapses automatically on load and the toggle re-expands it.
 */
export default function Sidebar() {
  const collapsed = useModuleStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useModuleStore((s) => s.toggleSidebar);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return;
    }
    const media = window.matchMedia(MOBILE_QUERY);
    const apply = () =>
      useModuleStore.getState().setSidebarCollapsed(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  return (
    <aside
      aria-label="Sidebar"
      className={`flex h-full shrink-0 flex-col border-r border-gray-200 bg-white transition-[width] duration-200 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      <div className="flex h-16 shrink-0 items-center border-b border-gray-200 px-3">
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label="Toggle sidebar"
          aria-expanded={!collapsed}
          className="rounded-md p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className="h-5 w-5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
      </div>
      <nav
        id="main-navigation"
        aria-label="Main navigation"
        className="flex-1 overflow-y-auto p-3"
      >
        {NAV_GROUPS.map((group) => (
          <NavGroup
            key={group.title}
            title={group.title}
            items={group.items}
            collapsed={collapsed}
          />
        ))}
      </nav>
    </aside>
  );
}