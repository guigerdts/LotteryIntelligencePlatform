import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Backtesting from "./Backtesting";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status }
  );

const runResult = {
  snapshot_id: 9,
  lottery_id: 1,
  strategy_id: "uniform-weighted",
  fingerprint: "fp-bt-123",
  version: "v1",
  status: "completed",
};

const resultData = {
  snapshot_id: 9,
  lottery_id: 1,
  strategy_id: "uniform-weighted",
  fingerprint: "fp-bt-123",
  version: "v1",
  status: "completed",
  aggregate_metrics: {
    hit_rate: 0.42,
    average_matches: 2.75,
    consistency_score: 0.81,
    total_draws_evaluated: 240,
  },
  window_history: [],
};

let runCalls = 0;
let resultsCalls = 0;

const server = setupServer(
  http.post("*/api/v1/backtesting/run", () => {
    runCalls += 1;
    return env(runResult);
  }),
  http.get("*/api/v1/backtesting/results", () => {
    resultsCalls += 1;
    return env(resultData);
  })
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  runCalls = 0;
  resultsCalls = 0;
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

describe("Backtesting", () => {
  it("renders the form with all backtest fields", async () => {
    selectLottery();
    render(<Backtesting />);
    expect(await screen.findByRole("heading", { name: /backtesting/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/strategy id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/años de entrenamiento/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/evaluaciones/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/pasos/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/sorteos mínimos de entrenamiento/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/semilla/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^ejecutar prueba histórica$/i })).toBeInTheDocument();
  });

  it("runs a backtest and renders the aggregate metrics", async () => {
    selectLottery();
    render(<Backtesting />);
    await screen.findByRole("heading", { name: /backtesting/i });
    fireEvent.change(screen.getByLabelText(/strategy id/i), {
      target: { value: "uniform-weighted" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^ejecutar prueba histórica$/i }));
    const resultSection = await screen.findByLabelText(/resultado de la prueba histórica/i);
    expect(within(resultSection).getByText("#9")).toBeInTheDocument();
    expect(within(resultSection).getByText("uniform-weighted")).toBeInTheDocument();
    expect(within(resultSection).getByText("fp-bt-123")).toBeInTheDocument();
    expect(within(resultSection).getByText("42.0%")).toBeInTheDocument();
    expect(within(resultSection).getByText("2.75")).toBeInTheDocument();
    expect(within(resultSection).getByText("0.81")).toBeInTheDocument();
    expect(within(resultSection).getByText("240")).toBeInTheDocument();
    expect(runCalls).toBe(1);
    expect(resultsCalls).toBe(1);
  });

  it("disables the button and shows a skeleton while running", async () => {
    selectLottery();
    server.use(http.post("*/api/v1/backtesting/run", () => delay(50).then(() => env(runResult))));
    render(<Backtesting />);
    await screen.findByRole("heading", { name: /backtesting/i });
    fireEvent.change(screen.getByLabelText(/strategy id/i), {
      target: { value: "uniform-weighted" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^ejecutar prueba histórica$/i }));
    const button = screen.getByRole("button", { name: /ejecutando/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(await screen.findByText("#9")).toBeInTheDocument();
  });

  it("shows an error state and recovers via the retry button", async () => {
    selectLottery();
    server.use(http.post("*/api/v1/backtesting/run", () => err("Server error")));
    render(<Backtesting />);
    await screen.findByRole("heading", { name: /backtesting/i });
    fireEvent.change(screen.getByLabelText(/strategy id/i), {
      target: { value: "uniform-weighted" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^ejecutar prueba histórica$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument();
    server.use(http.post("*/api/v1/backtesting/run", () => env(runResult)));
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(screen.getByText("42.0%")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Backtesting />);
    expect(await screen.findByText(/selecciona una lotería para ejecutar una prueba histórica/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^ejecutar prueba histórica$/i })).toBeDisabled();
    expect(runCalls).toBe(0);
    expect(resultsCalls).toBe(0);
  });
});
