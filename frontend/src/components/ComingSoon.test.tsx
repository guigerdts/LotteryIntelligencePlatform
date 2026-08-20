import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ComingSoon from "./ComingSoon";

describe("ComingSoon", () => {
  it("renders the page heading with the given title", () => {
    render(<ComingSoon title="Generator" />);

    expect(
      screen.getByRole("heading", { name: "Generator" }),
    ).toBeInTheDocument();
  });

  it("renders the coming-soon empty state with the title interpolated", () => {
    render(<ComingSoon title="Optimization" />);

    expect(
      screen.getByText(/Próximamente — Optimization disponible en una futura fase\./),
    ).toBeInTheDocument();
  });
});