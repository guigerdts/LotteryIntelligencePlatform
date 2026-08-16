import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Heatmaps from "./Heatmaps";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) => HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) => HttpResponse.json({ success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" }, { status });

const snapshot = (id: number, extra: Record<string, unknown> = {}) => ({
  snapshot_id: id,
  version: "v1",
  status: "ready",
  draw_count: 100,
  created_at: "2026-01-01T00:00:00Z",
  ...extra,
});

const coo = (subject: string, value: number) => ({ metric_type: "cooccurrence", subject, draw_number: null, value });

const snap2Values = [coo("1-2", 5), coo("1-3", 2), coo("2-3", 4), { metric_type: "centrality_degree", subject: "1", draw_number: null, value: 0.5 }];
const snap1Values = [coo("1-2", 1), coo("1-4", 3)];
const snap3Values = [coo("2-4", 7)];
const computeResult = { snapshot_id: 3, lottery_code: "L1", version: "v1", graph_type: "cooccurrence", graph_generator_version: "g1", draws_from: 1, draws_to: 120, draw_count: 120, checksum: "abc", fingerprint: "fp3" };

let snapshotCalls = 0;
let computeCalls = 0;
let valuesRequests: number[] = [];

const snapList = () => ({
  snapshots: [snapshot(2, { version: "v2", draw_count: 150, created_at: "2026-02-01T00:00:00Z" }), snapshot(1)],
});

const server = setupServer(
  http.get("*/api/v1/graph/L1/snapshots", () => {
    snapshotCalls += 1;
    return env(snapList());
  }),
  http.get("*/api/v1/graph/L1/snapshots/1", () => {
    valuesRequests.push(1);
    return env({ rows: snap1Values, count: snap1Values.length });
  }),
  http.get("*/api/v1/graph/L1/snapshots/2", () => {
    valuesRequests.push(2);
    return env({ rows: snap2Values, count: snap2Values.length });
  }),
  http.get("*/api/v1/graph/L1/snapshots/3", () => {
    valuesRequests.push(3);
    return env({ rows: snap3Values, count: snap3Values.length });
  }),
  http.post("*/api/v1/graph/compute", () => {
    computeCalls += 1;
    return env(computeResult);
  }),
);

const selectLottery = () => useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  snapshotCalls = 0;
  computeCalls = 0;
  valuesRequests = [];
  localStorage.clear();
  useLotteryStore.setState({ lotteries: [], selectedLotteryId: null, selectedLotteryCode: null, isLoading: false, error: null });
});
afterAll(() => server.close());

describe("Heatmaps", () => {
  it("renders the heatmap grid on mount, auto-selecting the latest snapshot", async () => {
    selectLottery();
    render(<Heatmaps />);
    expect(await screen.findByRole("heading", { name: /heatmaps/i })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /co-occurrence heatmap/i })).toBeInTheDocument();
    await waitFor(() => expect(valuesRequests).toContain(2));
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("3", { selector: "span.font-medium" })).toBeInTheDocument();
  });

  it("selecting another snapshot updates the grid", async () => {
    selectLottery();
    render(<Heatmaps />);
    await screen.findByRole("img", { name: /co-occurrence heatmap/i });
    fireEvent.click(screen.getByRole("button", { name: /#1/i }));
    await waitFor(() => expect(valuesRequests[valuesRequests.length - 1]).toBe(1));
    expect(screen.getByRole("button", { name: /#1/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("computes a snapshot via POST and refreshes the list", async () => {
    selectLottery();
    render(<Heatmaps />);
    await screen.findByRole("img", { name: /co-occurrence heatmap/i });
    fireEvent.click(screen.getByRole("button", { name: /^compute$/i }));
    await waitFor(() => expect(computeCalls).toBe(1));
    await waitFor(() => expect(snapshotCalls).toBeGreaterThanOrEqual(2));
    expect(await screen.findByRole("img", { name: /co-occurrence heatmap/i })).toBeInTheDocument();
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/graph/L1/snapshots", () => delay(50).then(() => env(snapList()))));
    const { container } = render(<Heatmaps />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(await screen.findByRole("img", { name: /co-occurrence heatmap/i })).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/graph/L1/snapshots", () => err("Server error")));
    render(<Heatmaps />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/graph/L1/snapshots", () => env(snapList())));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByRole("img", { name: /co-occurrence heatmap/i })).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Heatmaps />);
    expect(await screen.findByText(/select a lottery to see co-occurrence heatmaps/i)).toBeInTheDocument();
    expect(snapshotCalls).toBe(0);
    expect(computeCalls).toBe(0);
    expect(screen.getByRole("button", { name: /^compute$/i })).toBeDisabled();
  });
});