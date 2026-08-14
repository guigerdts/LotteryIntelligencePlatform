import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useModuleStore } from "../store/useModuleStore";
import Sidebar from "./Sidebar";

const ALL_ITEMS = [
  { label: "Inicio", to: "/" },
  { label: "Historial", to: "/historial" },
  { label: "Estadísticas", to: "/estadisticas" },
  { label: "Heatmaps", to: "/heatmaps" },
  { label: "Tendencias", to: "/tendencias" },
  { label: "Monte Carlo", to: "/monte-carlo" },
  { label: "Redes", to: "/redes" },
  { label: "IA", to: "/ia" },
  { label: "Modelos", to: "/modelos" },
  { label: "Experimentos", to: "/experimentos" },
  { label: "Backtesting", to: "/backtesting" },
  { label: "Generador", to: "/generador" },
];

function renderSidebar(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

afterEach(() => {
  useModuleStore.setState({ sidebarCollapsed: false });
});

describe("Sidebar", () => {
  it("renders the five navigation groups with their titles", () => {
    renderSidebar();

    const headings = [
      "General",
      "Análisis",
      "Avanzado",
      "ML",
      "Generador",
    ];
    for (const title of headings) {
      expect(
        screen.getByRole("heading", { name: title }),
      ).toBeInTheDocument();
    }
  });

  it("renders every navigation item with its route", () => {
    renderSidebar();

    for (const { label, to } of ALL_ITEMS) {
      const link = screen.getByRole("link", { name: label });
      expect(link).toHaveAttribute("href", to);
    }
  });

  it("exposes a navigation landmark", () => {
    renderSidebar();

    expect(
      screen.getByRole("navigation", { name: "Main navigation" }),
    ).toBeInTheDocument();
  });

  it("marks the active route with aria-current=page", () => {
    renderSidebar("/estadisticas");

    expect(
      screen.getByRole("link", { name: "Estadísticas" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Inicio" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("does not mark the root link as active on nested routes", () => {
    renderSidebar("/modelos");

    expect(
      screen.getByRole("link", { name: "Modelos" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Inicio" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("collapses and re-expands through the toggle", () => {
    renderSidebar();

    const aside = screen.getByRole("complementary", { name: "Sidebar" });
    const toggle = screen.getByRole("button", { name: "Toggle sidebar" });

    expect(aside).toHaveClass("w-64");
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(toggle);

    expect(aside).toHaveClass("w-16");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps labels in the accessibility tree when collapsed", () => {
    renderSidebar();

    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));

    for (const { label } of ALL_ITEMS) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });
});
