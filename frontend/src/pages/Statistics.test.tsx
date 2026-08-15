import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Statistics from "./Statistics";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status },
  );
const header = (extra: Record<string, unknown>) => ({
  snapshot_id: 1,
  lottery_code: "L1",
  version: "v1",
  generator_version: "g1",
  draws_from: 1,
  draws_to: 100,
  draw_count: 100,
  checksum: "abc",
  ...extra,
});
const frequencyList = header({
  frequencies: [
    { number: 5, count: 14 },
    { number: 7, count: 11 },
    { number: 9, count: 9 },
    { number: 12, count: 8 },
    { number: 3, count: 7 },
  ],
});
const gapList = header({
  gaps: [{ number: 5, count: 14, min_gap: 1, max_gap: 12, avg_gap: 4.5 }],
});
const averageList = header({ averages: { sum: { mean: 42.5, non_null_count: 90 } } });
const snapshot = header({ snapshot_id: 2, checksum: "def", metric_set: "freq", incremental: true });

let fetchCalls = 0;
let generateCalls = 0;

const server = setupServer(
  http.get("*/api/v1/statistics/L1/frequencies", () => {
    fetchCalls += 1;
    return env(frequencyList);
  }),
  http.get("*/api/v1/statistics/L1/gaps", () => {
    fetchCalls += 1;
    return env(gapList);
  }),
  http.get("*/api/v1/statistics/L1/averages", () => {
    fetchCalls += 1;
    return env(averageList);
  }),
  http.post("*/api/v1/statistics/generate", () => {
    generateCalls += 1;
    return env(snapshot);
  }),
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  fetchCalls = 0;
  generateCalls = 0;
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

describe("Statistics", () => {
  it("renders the frequency chart with snapshot summary", async () => {
    selectLottery();
    render(<Statistics />);
    expect(await screen.findByRole("heading", { name: /statistics/i })).toBeInTheDocument();
    expect(
      await screen.findByRole("img", { name: /frequency distribution per number/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("1–100")).toBeInTheDocument();
  });

  it("switches tabs to gap and average charts", async () => {
    selectLottery();
    render(<Statistics />);
    await screen.findByRole("img", { name: /frequency distribution per number/i });
    fireEvent.click(screen.getByRole("tab", { name: /gaps/i }));
    expect(
      await screen.findByRole("img", { name: /gap analysis per number/i }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /averages/i }));
    expect(
      await screen.findByRole("img", { name: /average gap per series/i }),
    ).toBeInTheDocument();
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/statistics/L1/frequencies", () => delay(50).then(() => env(frequencyList))),
    );
    const { container } = render(<Statistics />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/statistics/L1/frequencies", () => err("Server error")));
    render(<Statistics />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/statistics/L1/frequencies", () => env(frequencyList)));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() =>
      expect(
        screen.getByRole("img", { name: /frequency distribution per number/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an empty state instead of crashing when frequencies are empty", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/statistics/L1/frequencies", () => env(header({ frequencies: [] }))),
    );
    render(<Statistics />);
    expect(
      await screen.findByText(/no statistics available for this lottery/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Statistics />);
    expect(
      await screen.findByText(/select a lottery to see its statistics/i),
    ).toBeInTheDocument();
    expect(fetchCalls).toBe(0);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate snapshot/i })).toBeDisabled();
  });

  it("generates a snapshot via POST for the selected lottery", async () => {
    selectLottery();
    render(<Statistics />);
    fireEvent.click(await screen.findByRole("button", { name: /generate snapshot/i }));
    await waitFor(() => expect(generateCalls).toBe(1));
  });
});