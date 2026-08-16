import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import IA from "./IA";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500) =>
  HttpResponse.json(
    { success: false, error: { code: "INTERNAL_ERROR", message }, timestamp: "" },
    { status },
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
const probabilityList = {
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

let modelsCalls = 0;
let metricsCalls = 0;
let probCalls = 0;

const server = setupServer(
  http.get("*/api/v1/health", () => env({ status: "ok" })),
  http.get("*/api/v1/version", () => env({ version: "1.0.0", app: "Lottery Intelligence Platform" })),
  http.get("*/api/v1/ml/models", () => {
    modelsCalls += 1;
    return env(snapshot);
  }),
  http.get("*/api/v1/ml/metrics", () => {
    metricsCalls += 1;
    return env(metrics);
  }),
  http.get("*/api/v1/probability/L1/probabilities", () => {
    probCalls += 1;
    return env(probabilityList);
  }),
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  modelsCalls = 0;
  metricsCalls = 0;
  probCalls = 0;
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

describe("IA", () => {
  it("renders system, model and probability status on mount", async () => {
    selectLottery();
    render(<IA />);
    expect(await screen.findByRole("heading", { name: /ai assistant/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "System status" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Model status" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Recent probabilities" })).toBeInTheDocument();
    expect(await screen.findByText("ok")).toBeInTheDocument();
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
    expect(await screen.findByText("core-5")).toBeInTheDocument();
    expect(screen.getByText("0.8421")).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getAllByText("baseline").length).toBeGreaterThan(0);
    expect(within(table).getByText("0.1420")).toBeInTheDocument();
  });

  it("shows an error with retry for the model section and recovers", async () => {
    selectLottery();
    server.use(http.get("*/api/v1/ml/models", () => err("Server error")));
    render(<IA />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/server error/i);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/ml/models", () => env(snapshot)));
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText("core-5")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows skeleton placeholders while sections load", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/probability/L1/probabilities", () => delay(50).then(() => env(probabilityList))),
    );
    const { container } = render(<IA />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call lottery-scoped endpoints", async () => {
    render(<IA />);
    expect(
      (await screen.findAllByText(/select a lottery to see the ai assistant/i)).length,
    ).toBeGreaterThan(0);
    expect(modelsCalls).toBe(0);
    expect(metricsCalls).toBe(0);
    expect(probCalls).toBe(0);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});