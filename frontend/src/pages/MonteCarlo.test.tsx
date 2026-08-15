import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import MonteCarlo from "./MonteCarlo";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status },
  );

const list = {
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
    { model_id: "baseline", model_version: "v1", subject: "23", draw_number: 101, value: "0.1105" },
  ],
};
const snapshot = {
  snapshot_id: 3,
  lottery_code: "L1",
  version: "v1",
  model_set: "baseline",
  prob_generator_version: "pg1",
  draws_from: 1,
  draws_to: 100,
  draw_count: 100,
  checksum: "abc",
  incremental: true,
};

let fetchCalls = 0;
let generateCalls = 0;

const server = setupServer(
  http.get("*/api/v1/probability/L1/probabilities", () => {
    fetchCalls += 1;
    return env(list);
  }),
  http.post("*/api/v1/probability/generate", () => {
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

describe("MonteCarlo", () => {
  it("renders the probability table on mount", async () => {
    selectLottery();
    render(<MonteCarlo />);
    expect(await screen.findByRole("heading", { name: /monte carlo/i })).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getAllByText("baseline")).toHaveLength(2);
    expect(within(table).getByText("5")).toBeInTheDocument();
    expect(within(table).getByText("0.1420")).toBeInTheDocument();
  });

  it("calls POST generate and refreshes probabilities", async () => {
    selectLottery();
    render(<MonteCarlo />);
    await screen.findByRole("table");
    fireEvent.click(screen.getByRole("button", { name: /^generate$/i }));
    await waitFor(() => expect(generateCalls).toBe(1));
    await waitFor(() => expect(fetchCalls).toBeGreaterThanOrEqual(2));
    expect(await screen.findByText("#3")).toBeInTheDocument();
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/probability/L1/probabilities", () => delay(50).then(() => env(list))),
    );
    const { container } = render(<MonteCarlo />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/probability/L1/probabilities", () => err("Server error")));
    render(<MonteCarlo />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/probability/L1/probabilities", () => env(list)));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<MonteCarlo />);
    expect(
      await screen.findByText(/select a lottery to see probability rows/i),
    ).toBeInTheDocument();
    expect(fetchCalls).toBe(0);
    expect(generateCalls).toBe(0);
    expect(screen.getByRole("button", { name: /^generate$/i })).toBeDisabled();
  });
});