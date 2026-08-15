import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Generator from "./Generator";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const genError = (code: string, message: string, status = 422) =>
  HttpResponse.json(
    { success: false, error: { code, message }, timestamp: "" },
    { status },
  );

const result = {
  snapshot_id: 7,
  lottery_id: 1,
  selection_id: 0,
  version: "v1",
  status: "active",
  fingerprint: "fp-abc123",
  seed: 42,
  count: 2,
  combinations: [
    { position: 1, numbers: [3, 12, 27, 34, 45, 49], super_number: 8, score: 0.82 },
    { position: 2, numbers: [5, 11, 22, 30, 41, 48], super_number: null, score: null },
  ],
};

let generateCalls = 0;

const server = setupServer(
  http.post("*/api/v1/gen/generate", () => {
    generateCalls += 1;
    return env(result);
  }),
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
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

describe("Generator", () => {
  it("renders the form with count, seed and selection inputs", async () => {
    selectLottery();
    render(<Generator />);
    expect(await screen.findByRole("heading", { name: /generator/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/count/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/seed/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/selection id/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^generate$/i })).toBeInTheDocument();
  });

  it("generates combinations and renders the snapshot inline", async () => {
    selectLottery();
    render(<Generator />);
    fireEvent.change(screen.getByLabelText(/count/i), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/seed/i), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: /^generate$/i }));
    const table = await screen.findByRole("table");
    expect(within(table).getByText("3 - 12 - 27 - 34 - 45 - 49")).toBeInTheDocument();
    expect(within(table).getByText("8")).toBeInTheDocument();
    expect(screen.getByText("#7")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("fp-abc123")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("disables the button and shows a spinner while generating", async () => {
    selectLottery();
    server.use(http.post("*/api/v1/gen/generate", () => delay(50).then(() => env(result))));
    render(<Generator />);
    fireEvent.click(screen.getByRole("button", { name: /^generate$/i }));
    const button = screen.getByRole("button", { name: /generating/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /^generate$/i })).toBeEnabled();
  });

  it("maps GEN_COUNT_INVALID to a user-friendly message", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/gen/generate", () => genError("GEN_COUNT_INVALID", "count must be >= 1")),
    );
    render(<Generator />);
    fireEvent.change(screen.getByLabelText(/count/i), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: /^generate$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /count must be between 1 and 100/i,
    );
  });

  it("recovers from an error via the retry button", async () => {
    selectLottery();
    server.use(http.post("*/api/v1/gen/generate", () => genError("GEN_SPACE_EXHAUSTED", "space")));
    render(<Generator />);
    fireEvent.click(screen.getByRole("button", { name: /^generate$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/generation space exhausted/i);
    server.use(http.post("*/api/v1/gen/generate", () => env(result)));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and disables the form without calling the API", async () => {
    render(<Generator />);
    expect(
      await screen.findByText(/select a lottery to generate combinations/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^generate$/i })).toBeDisabled();
    expect(generateCalls).toBe(0);
  });
});
