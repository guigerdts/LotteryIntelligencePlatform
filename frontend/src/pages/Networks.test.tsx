import { describe, it, expect, beforeAll, afterAll, afterEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Networks from "./Networks";
import { useLotteryStore } from "../store/useLotteryStore";

const { forceGraphProps } = vi.hoisted(() => ({
  forceGraphProps: { nodes: [] as unknown[], links: [] as unknown[] },
}));

vi.mock("react-force-graph-2d", () => ({
  default: (props: { graphData: { nodes: unknown[]; links: unknown[] } }) => {
    forceGraphProps.nodes = props.graphData.nodes;
    forceGraphProps.links = props.graphData.links;
    return <div data-testid="mock-force-graph" />;
  },
}));

const env = (data: unknown) => HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) => HttpResponse.json({ success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" }, { status });

const snapshot = (id: number, extra: Record<string, unknown> = {}) => ({
  snapshot_id: id,
  lottery_code: "L1",
  version: "v1",
  graph_type: "network",
  status: "ready",
  draw_count: 100,
  created_at: "2026-01-01T00:00:00Z",
  ...extra,
});

const coo = (subject: string, value: number) => ({ metric_type: "cooccurrence", subject, draw_number: null, value });
const centrality = (subject: string, value: number) => ({ metric_type: "centrality_degree", subject, draw_number: null, value });
const community = (subject: string, value: number) => ({ metric_type: "community_id", subject, draw_number: null, value });

const snap2Values = [
  coo("1-2", 5),
  coo("1-3", 2),
  coo("2-3", 4),
  centrality("1", 0.8),
  centrality("2", 0.5),
  centrality("3", 0.3),
  community("1", 0),
  community("2", 0),
  community("3", 1),
  { metric_type: "density", subject: "graph", draw_number: null, value: 0.5 },
];
const snap1Values = [coo("1-2", 1), coo("1-4", 3), centrality("1", 0.6), centrality("4", 0.2)];

let snapshotCalls = 0;
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
);

const selectLottery = () => useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  snapshotCalls = 0;
  valuesRequests = [];
  forceGraphProps.nodes = [];
  forceGraphProps.links = [];
  localStorage.clear();
  useLotteryStore.setState({ lotteries: [], selectedLotteryId: null, selectedLotteryCode: null, isLoading: false, error: null });
});
afterAll(() => server.close());

describe("Networks", () => {
  it("renders the network graph on mount, auto-selecting the latest snapshot", async () => {
    selectLottery();
    render(<Networks />);
    expect(await screen.findByRole("heading", { name: /networks/i })).toBeInTheDocument();
    expect(await screen.findByTestId("network-graph")).toBeInTheDocument();
    await waitFor(() => {
      expect(valuesRequests).toContain(2);
      expect(forceGraphProps.links.length).toBe(3);
      expect(forceGraphProps.nodes.length).toBe(3);
      expect((forceGraphProps.nodes[0] as { color?: string }).color).toBeTruthy();
    });
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getAllByText("3", { selector: "span.font-medium" })).toHaveLength(2);
  });

  it("selecting another snapshot fetches its values and updates the graph", async () => {
    selectLottery();
    render(<Networks />);
    await screen.findByTestId("network-graph");
    fireEvent.click(screen.getByRole("button", { name: /#1/i }));
    await waitFor(() => expect(valuesRequests[valuesRequests.length - 1]).toBe(1));
    expect(screen.getByRole("button", { name: /#1/i })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => {
      expect(forceGraphProps.links.length).toBe(2);
      expect(forceGraphProps.nodes.length).toBe(3);
    });
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/graph/L1/snapshots", () => delay(50).then(() => env(snapList()))));
    const { container } = render(<Networks />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(await screen.findByTestId("network-graph")).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/graph/L1/snapshots", () => err("Server error")));
    render(<Networks />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/graph/L1/snapshots", () => env(snapList())));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByTestId("network-graph")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Networks />);
    expect(await screen.findByText(/select a lottery to see the network graph/i)).toBeInTheDocument();
    expect(snapshotCalls).toBe(0);
  });
});