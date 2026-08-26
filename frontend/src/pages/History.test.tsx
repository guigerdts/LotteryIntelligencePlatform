import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import History from "./History";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Draw } from "../types/draw";

const PAGE_SIZE = 50;

const ASYNC_TIMEOUT = { timeout: 10000 };

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });

const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status }
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
    { position: 2, number: 12 },
    { position: 3, number: 22 },
  ],
  super_number: 3,
});

const drawRange = (startId: number, startNumber: number, count: number): Draw[] =>
  Array.from({ length: count }, (_, index) => draw(startId + index, startNumber - index));

let drawsCalls = 0;

const server = setupServer(
  http.get("*/api/v1/draws", ({ request }) => {
    drawsCalls += 1;
    const url = new URL(request.url);
    const page = Number(url.searchParams.get("page") ?? "1");
    return page === 1 ? env(drawRange(200, 200, PAGE_SIZE)) : env(drawRange(150, 150, 3));
  })
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());

afterEach(() => {
  server.resetHandlers();
  drawsCalls = 0;
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

describe("History", () => {
  it("renders the paginated draw table for the selected lottery", async () => {
    selectLottery();
    render(<History />);

    expect(
      await screen.findByRole("heading", { name: /history/i }, ASYNC_TIMEOUT)
    ).toBeInTheDocument();
    const table = await screen.findByRole("table", {}, ASYNC_TIMEOUT);
    expect(within(table).getByText("200")).toBeInTheDocument();
    expect(within(table).getAllByText("5 - 12 - 22")).not.toHaveLength(0);
    expect(screen.getByText("Page 1")).toBeInTheDocument();
  });

  it("pages forward and backward with previous/next controls", async () => {
    selectLottery();
    render(<History />);

    const next = await screen.findByRole("button", { name: /next/i }, ASYNC_TIMEOUT);
    const previous = screen.getByRole("button", { name: /previous/i });
    expect(previous).toBeDisabled();
    expect(next).toBeEnabled();

    fireEvent.click(next);
    expect(await screen.findByText("Page 2", {}, ASYNC_TIMEOUT)).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.queryByText("200")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /previous/i })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: /previous/i }));
    expect(await screen.findByText("Page 1", {}, ASYNC_TIMEOUT)).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument();
    expect(screen.queryByText("150")).not.toBeInTheDocument();
  });

  it("shows skeleton placeholders while draws are loading", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/draws", () => delay(50).then(() => env(drawRange(200, 200, PAGE_SIZE))))
    );
    const { container } = render(<History />);

    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => {
      expect(container.querySelector(".animate-pulse")).toBeNull();
    });
    expect(screen.getByText("200")).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/draws", () => err("Server error")));
    render(<History />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument();

    server.use(http.get("*/api/v1/draws", () => env(drawRange(200, 200, PAGE_SIZE))));
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    await waitFor(() => {
      expect(screen.getByRole("table")).toHaveTextContent("200");
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an empty state when the lottery has no draws", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/draws", () => env([])));
    render(<History />);

    expect(      await screen.findByText(/no hay sorteos disponibles para esta lotería/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<History />);

    expect(
      await screen.findByText(/selecciona una lotería para ver el historial de sorteos/i)
    ).toBeInTheDocument();
    expect(drawsCalls).toBe(0);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
