import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Trends from "./Trends";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Draw } from "../types/draw";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status },
  );

const draw = (id: number, drawNumber: number): Draw => ({
  id,
  lottery_id: 1,
  draw_number: drawNumber,
  draw_date: "2026-07-01",
  jackpot: null,
  winners: 0,
  is_deleted: false,
  created_at: "2026-07-01T00:00:00Z",
  numbers: [
    { position: 1, number: 5 },
    { position: 2, number: 7 },
    { position: 3, number: 9 },
    { position: 4, number: 10 + (id % 5) },
  ],
  super_number: 3,
});

const drawRange = (count: number): Draw[] =>
  Array.from({ length: count }, (_, i) => draw(200 - i, 200 - i));

const frequencyList = {
  snapshot_id: 1,
  lottery_code: "L1",
  version: "v1",
  generator_version: "g1",
  draws_from: 176,
  draws_to: 200,
  draw_count: 25,
  checksum: "abc",
  frequencies: [
    { number: 5, count: 25 },
    { number: 7, count: 25 },
    { number: 9, count: 25 },
    { number: 10, count: 6 },
    { number: 11, count: 5 },
  ],
};

let fetchCalls = 0;

const server = setupServer(
  http.get("*/api/v1/draws", () => {
    fetchCalls += 1;
    return env(drawRange(25));
  }),
  http.get("*/api/v1/statistics/L1/frequencies", () => {
    fetchCalls += 1;
    return env(frequencyList);
  }),
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  fetchCalls = 0;
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

describe("Trends", () => {
  it("renders hot/cold numbers, trend chart and frequency chart on mount", async () => {
    selectLottery();
    render(<Trends />);
    expect(await screen.findByRole("heading", { name: /trends/i })).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Rolling frequency trend of hot numbers over recent draws",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Frequency distribution per number" }),
    ).toBeInTheDocument();
    const hot = screen.getByRole("region", { name: "Hot numbers" });
    expect(within(hot).getAllByText("25×").length).toBeGreaterThan(0);
    const cold = screen.getByRole("region", { name: "Cold numbers" });
    expect(within(cold).getByText("10")).toBeInTheDocument();
  });

  it("falls back to window-derived frequencies when the snapshot is missing (404)", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/statistics/L1/frequencies", () =>
        HttpResponse.json(
          { success: false, error: { code: "RESOURCE_NOT_FOUND", message: "No snapshot" }, timestamp: "" },
          { status: 404 },
        ),
      ),
    );
    render(<Trends />);
    expect(
      await screen.findByRole("img", {
        name: "Rolling frequency trend of hot numbers over recent draws",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Frequency distribution per number" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows skeleton placeholders while draws are loading", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/draws", () => delay(50).then(() => env(drawRange(25)))),
    );
    const { container } = render(<Trends />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(
      screen.getByRole("img", {
        name: "Rolling frequency trend of hot numbers over recent draws",
      }),
    ).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/draws", () => err("Server error")));
    render(<Trends />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/draws", () => env(drawRange(25))));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() =>
      expect(
        screen.getByRole("img", {
          name: "Rolling frequency trend of hot numbers over recent draws",
        }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Trends />);
    expect(
      await screen.findByText(/select a lottery to see its trends/i),
    ).toBeInTheDocument();
    expect(fetchCalls).toBe(0);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});