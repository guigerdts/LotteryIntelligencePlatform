import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import Models from "./Models";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status }
  );

const snapshot = {
  id: 3,
  lottery_id: 1,
  model_set: "core-5",
  version: "v1",
  status: "active",
  checksum: "abc",
  input_fingerprint: "fp1",
  cut: 1200,
};
const metrics = [
  { model_id: "rf", number: 5, metric_name: "accuracy", value: 0.8421, params_json: "{}" },
  { model_id: "rf", number: 23, metric_name: "accuracy", value: 0.8104, params_json: "{}" },
  { model_id: "knn", number: 5, metric_name: "f1", value: 0.7932, params_json: "{}" },
];
const trainResult = {
  lottery_id: 1,
  results: [
    {
      family: "rf",
      status: "active",
      snapshot_id: 3,
      fingerprint: "fp1",
      metrics_checksum: "mc1",
      error: null,
    },
  ],
};

let modelsCalls = 0;
let metricsCalls = 0;
let trainCalls = 0;

const server = setupServer(
  http.get("*/api/v1/ml/models", () => {
    modelsCalls += 1;
    return env(snapshot);
  }),
  http.get("*/api/v1/ml/metrics", () => {
    metricsCalls += 1;
    return env(metrics);
  }),
  http.post("*/api/v1/ml/train", () => {
    trainCalls += 1;
    return env(trainResult);
  })
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  modelsCalls = 0;
  metricsCalls = 0;
  trainCalls = 0;
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

describe("Models", () => {
  it("renders the model snapshot and metrics table on mount", async () => {
    selectLottery();
    render(<Models />);
    expect(await screen.findByRole("heading", { name: /models/i })).toBeInTheDocument();
    expect(await screen.findByText("core-5")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getAllByText("rf")).toHaveLength(2);
    expect(within(table).getByText("0.8421")).toBeInTheDocument();
    expect(within(table).getByText("knn")).toBeInTheDocument();
  });

  it("calls POST train and refreshes models and metrics", async () => {
    selectLottery();
    render(<Models />);
    await screen.findByRole("table");
    fireEvent.click(screen.getByRole("button", { name: /^entrenar$/i }));
    await waitFor(() => expect(trainCalls).toBe(1));
    await waitFor(() => expect(modelsCalls).toBeGreaterThanOrEqual(2));
    await waitFor(() => expect(metricsCalls).toBeGreaterThanOrEqual(2));
  });

  it("shows skeleton placeholders while data is loading", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/ml/models", () => delay(50).then(() => env(snapshot))));
    const { container } = render(<Models />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("shows an error state with retry and recovers on retry", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/ml/models", () => err("Server error")));
    render(<Models />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/ml/models", () => env(snapshot)));
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call the API", async () => {
    render(<Models />);
    expect(await screen.findByText(/selecciona una lotería para ver los modelos/i)).toBeInTheDocument();
    expect(modelsCalls).toBe(0);
    expect(metricsCalls).toBe(0);
    expect(trainCalls).toBe(0);
    expect(screen.getByRole("button", { name: /^entrenar$/i })).toBeDisabled();
  });
});
