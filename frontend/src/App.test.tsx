import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { routes } from "./App";
import { useLotteryStore } from "./store/useLotteryStore";

const ASYNC_TIMEOUT = { timeout: 10000 };

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });

const server = setupServer(
  http.get("*/api/v1/lotteries", () =>
    env([{ id: 1, code: "L1", name: "Loto", country: "ES" }]),
  ),
  http.get("*/api/v1/draws", () => env([])),
  http.get("*/api/v1/statistics/L1/frequencies", () =>
    env({
      snapshot_id: 1,
      lottery_code: "L1",
      version: "v1",
      generator_version: "g1",
      draws_from: 1,
      draws_to: 0,
      draw_count: 0,
      checksum: "x",
      frequencies: [],
    }),
  ),
  http.get("*/api/v1/health", () => env({ status: "ok" })),
  http.get("*/api/v1/version", () =>
    env({ version: "1.0.0", app: "Lottery Intelligence Platform" }),
  ),
  http.get("*/api/v1/ml/models", () =>
    env({
      id: 3,
      lottery_id: 1,
      model_set: "core-5",
      version: "v1",
      status: "active",
      checksum: "abc",
      input_fingerprint: "fp1",
      cut: 1200,
    }),
  ),
  http.get("*/api/v1/ml/metrics", () => env([])),
  http.get("*/api/v1/probability/L1/probabilities", () =>
    env({
      snapshot_id: 3,
      lottery_code: "L1",
      version: "v1",
      prob_generator_version: "pg1",
      draws_from: 1,
      draws_to: 100,
      draw_count: 100,
      checksum: "abc",
      probabilities: [
        { model_id: "baseline", model_version: "v1", subject: "5", draw_number: 101, value: "0.1420" },
      ],
    }),
  ),
);

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

beforeAll(() => server.listen());

afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
  useLotteryStore.setState({
    lotteries: [],
    selectedLotteryId: null,
    selectedLotteryCode: null,
    isLoading: false,
    error: null,
  });
});

afterAll(() => server.close());

describe("App router", () => {
  it("shows the Suspense fallback while a lazy page chunk loads", async () => {
    const { container } = renderAt("/");

    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    expect(
      await screen.findByRole("heading", { name: /operational summary/i }, ASYNC_TIMEOUT),
    ).toBeInTheDocument();
  }, 15000);

  it("renders a real page (Home) inside the dashboard layout with sidebar", async () => {
    useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });
    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: /operational summary/i }, ASYNC_TIMEOUT),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Main navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("complementary", { name: "Sidebar" }),
    ).toBeInTheDocument();
  }, 15000);

  it("navigates between routes through the sidebar links", async () => {
    useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });
    renderAt("/");

    await screen.findByRole("heading", { name: /operational summary/i }, ASYNC_TIMEOUT);
    fireEvent.click(screen.getByRole("link", { name: "Generador" }));

    expect(
      await screen.findByRole("heading", { name: "Generator" }, ASYNC_TIMEOUT),
    ).toBeInTheDocument();
  });

  it("renders a 404 fallback for unknown routes", async () => {
    renderAt("/unknown");

    expect(
      await screen.findByRole("heading", { name: /page not found/i }, ASYNC_TIMEOUT),
    ).toBeInTheDocument();
  });

  it("renders the real AI Assistant page at /ia", async () => {
    useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });
    renderAt("/ia");

    expect(
      await screen.findByRole("heading", { name: /ai assistant/i }, ASYNC_TIMEOUT),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "System status" }),
    ).toBeInTheDocument();
  }, 15000);
});
