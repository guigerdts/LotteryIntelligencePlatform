import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Home from "./Home";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Draw } from "../types/draw";
import type { FrequencyList } from "../types/statistics";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });

const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status },
  );

const draw = (
  id: number,
  drawNumber: number,
  drawDate: string,
  nums: number[],
  superNumber: number | null,
): Draw => ({
  id,
  lottery_id: 1,
  draw_number: drawNumber,
  draw_date: drawDate,
  jackpot: null,
  winners: 0,
  is_deleted: false,
  created_at: `${drawDate}T00:00:00Z`,
  numbers: nums.map((number, position) => ({ position: position + 1, number })),
  super_number: superNumber,
});

const draws: Draw[] = [
  draw(11, 101, "2026-07-01", [5, 12, 22], 3),
  draw(10, 100, "2026-06-28", [7, 9, 33], null),
];

const frequencyList: FrequencyList = {
  snapshot_id: 1,
  lottery_code: "L1",
  version: "v1",
  generator_version: "g1",
  draws_from: 1,
  draws_to: 100,
  draw_count: 100,
  checksum: "abc123",
  frequencies: [
    { number: 5, count: 14 },
    { number: 7, count: 11 },
    { number: 9, count: 9 },
    { number: 12, count: 8 },
    { number: 3, count: 7 },
    { number: 1, count: 2 },
    { number: 2, count: 1 },
  ],
};

const server = setupServer(
  http.get("*/api/v1/draws", () => env(draws)),
  http.get("*/api/v1/statistics/L1/frequencies", () => env(frequencyList)),
  http.get("*/api/v1/health", () => env({ status: "ok" })),
  http.get("*/api/v1/version", () =>
    env({ version: "1.0.0", app: "Lottery Intelligence Platform" }),
  ),
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

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

describe("Home", () => {
  it("renders latest draws, frequency summary and system health", async () => {
    selectLottery();
    render(<Home />);

    expect(
      await screen.findByRole("heading", { name: /latest draws/i }),
    ).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("101")).toBeInTheDocument();
    expect(within(table).getByText("100")).toBeInTheDocument();
    expect(within(table).getByText("5 - 12 - 22")).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: /frequency summary/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Most frequent")).toBeInTheDocument();
    expect(screen.getByText("Least frequent")).toBeInTheDocument();
    expect(screen.getByText("14×")).toBeInTheDocument();
    expect(screen.getByText("1×")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: /^system$/i })).toBeInTheDocument();
    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/draws", () => delay(50).then(() => env(draws))));
    const { container } = render(<Home />);

    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => {
      expect(container.querySelector(".animate-pulse")).toBeNull();
    });
    expect(screen.getByText("101")).toBeInTheDocument();
  });

  it("shows an error state with retry when draws fail and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/draws", () => err("Server error")));
    render(<Home />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();

    server.use(http.get("*/api/v1/draws", () => env(draws)));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByRole("table")).toHaveTextContent("101");
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an empty state when the lottery has no draws", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/draws", () => env([])));
    render(<Home />);

    expect(
      await screen.findByText(/no data available for this lottery/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery when none is selected but still shows health", async () => {
    render(<Home />);

    expect(
      await screen.findAllByText(/select a lottery to see its operational summary/i),
    ).not.toHaveLength(0);
    expect(await screen.findByText("1.0.0")).toBeInTheDocument();
  });
});
