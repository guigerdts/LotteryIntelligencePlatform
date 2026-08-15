import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Experiments from "./Experiments";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status },
  );

const baseExperiment = {
  lottery_id: 1,
  fingerprint: "fp1",
  version: "v1",
  status: "active",
  config_json: null,
};

const experimentA = {
  ...baseExperiment,
  experiment_id: 1,
  name: "Baseline",
  description: "Initial run",
  created_at: "2026-01-02T00:00:00Z",
};
const experimentB = {
  ...baseExperiment,
  experiment_id: 2,
  name: "Boosted",
  description: null,
  status: "retired",
  created_at: "2026-01-03T00:00:00Z",
};

let listCalls = 0;
let createCalls = 0;
let created: Array<{
  experiment_id: number;
  lottery_id: number;
  name: string;
  description: string | null;
  fingerprint: string;
  version: string;
  status: string;
  config_json: null;
  created_at: string;
}> = [];

const server = setupServer(
  http.get("*/api/v1/experiment/", () => {
    listCalls += 1;
    return env([...created, experimentA, experimentB]);
  }),
  http.post("*/api/v1/experiment/create", async ({ request }) => {
    createCalls += 1;
    const body = (await request.json()) as { name: string; description?: string };
    const fresh = {
      ...baseExperiment,
      experiment_id: 3,
      name: body.name,
      description: body.description ?? null,
      created_at: "2026-01-04T00:00:00Z",
    };
    created = [fresh, ...created];
    return env(fresh);
  }),
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  listCalls = 0;
  createCalls = 0;
  created = [];
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

describe("Experiments", () => {
  it("renders the experiment list on mount", async () => {
    selectLottery();
    render(<Experiments />);
    expect(await screen.findByRole("heading", { name: /experiments/i })).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Baseline")).toBeInTheDocument();
    expect(within(table).getByText("Boosted")).toBeInTheDocument();
    expect(within(table).getByText("active")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
  });

  it("creates an experiment and refreshes the list", async () => {
    selectLottery();
    render(<Experiments />);
    await screen.findByRole("table");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Test" } });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "New run" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^create experiment$/i }));
    await waitFor(() => expect(createCalls).toBe(1));
    await waitFor(() => expect(listCalls).toBeGreaterThanOrEqual(2));
    expect(await screen.findByRole("table")).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Test")).toBeInTheDocument();
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/experiment/", () => delay(50).then(() => env([]))),
    );
    const { container } = render(<Experiments />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/experiment/", () => err("Server error")));
    render(<Experiments />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/experiment/", () => env([experimentA])));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows empty state when no experiments exist", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/experiment/", () => env([])));
    render(<Experiments />);
    expect(await screen.findByText(/no experiments yet/i)).toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Experiments />);
    expect(
      await screen.findByText(/select a lottery to see experiments/i),
    ).toBeInTheDocument();
    expect(listCalls).toBe(0);
    expect(createCalls).toBe(0);
    expect(screen.getByRole("button", { name: /^create experiment$/i })).toBeDisabled();
  });
});