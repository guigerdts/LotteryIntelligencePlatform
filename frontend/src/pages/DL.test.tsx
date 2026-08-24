import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import DL from "./DL";
import { getDlMetrics, getDlModels, trainDlModels } from "../services/dl";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500, code = "INTERNAL_ERROR") =>
  HttpResponse.json({ success: false, error: { code, message }, timestamp: "" }, { status });

const snapshot = {
  id: 7,
  lottery_id: 1,
  model_set: "core-3",
  version: "v1",
  status: "active",
  checksum: "cs1",
  input_fingerprint: "fp-dl",
  cut: 305,
  window: 10,
};
// lstm first on purpose: the page must pre-sort rows by model_id (R2).
const metrics = [
  { model_id: "lstm", number: 5, metric_name: "mae", value: 0.11, params_json: "{}" },
  { model_id: "mlp", number: 5, metric_name: "mae", value: 0.12, params_json: "{}" },
];
const trainResult = {
  lottery_id: 1,
  results: [
    {
      family: "mlp",
      status: "active",
      snapshot_id: 7,
      fingerprint: "fp-dl",
      metrics_checksum: "cs1",
      error: null,
    },
  ],
};

let modelsCalls = 0;
let metricsCalls = 0;
let trainCalls = 0;
let lastModelsUrl = "";
let lastMetricsUrl = "";
let lastTrainRequest: Request | null = null;

const server = setupServer(
  http.get("*/api/v1/dl/models", ({ request }) => {
    modelsCalls += 1;
    lastModelsUrl = request.url;
    return env(snapshot);
  }),
  http.get("*/api/v1/dl/metrics", ({ request }) => {
    metricsCalls += 1;
    lastMetricsUrl = request.url;
    return env(metrics);
  }),
  http.post("*/api/v1/dl/train", ({ request }) => {
    trainCalls += 1;
    lastTrainRequest = request;
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
  lastModelsUrl = "";
  lastMetricsUrl = "";
  lastTrainRequest = null;
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

describe("DL service client", () => {
  it("calls the /dl/* endpoints with ml.ts-mirrored shapes (R1-S1)", async () => {
    const snap = await getDlModels(1);
    expect(snap).toEqual(snapshot);
    expect(lastModelsUrl).toContain("/api/v1/dl/models?");
    expect(lastModelsUrl).toContain("lottery_id=1");

    const rows = await getDlMetrics(1);
    expect(rows).toEqual(metrics);
    expect(lastMetricsUrl).toContain("/api/v1/dl/metrics?");
    expect(lastMetricsUrl).toContain("lottery_id=1");

    const filtered = await getDlMetrics(1, "lstm");
    expect(filtered).toEqual(metrics);
    expect(lastMetricsUrl).toContain("model_id=lstm");

    const trained = await trainDlModels(1);
    expect(trained).toEqual(trainResult);
    expect(lastTrainRequest?.method).toBe("POST");
    expect(lastTrainRequest?.url).toContain("/api/v1/dl/train?");
    expect(lastTrainRequest?.url).toContain("lottery_id=1");
  });

  it("carries window through DLSnapshot (R1-S2)", async () => {
    server.use(http.get("*/api/v1/dl/models", () => env({ ...snapshot, cut: 305, window: 10 })));
    const result = await getDlModels(1);
    expect(result?.window).toBe(10);
    expect(result?.cut).toBe(305);
  });
});

describe("DL page", () => {
  it("renders the snapshot summary fields and model_id-grouped metric rows (R2-S1)", async () => {
    selectLottery();
    render(<DL />);
    expect(await screen.findByRole("heading", { name: /deep learning/i })).toBeInTheDocument();
    // Seven required summary fields (plus model_set).
    expect(screen.getByText("core-3")).toBeInTheDocument();
    expect(screen.getByText("#7")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("cs1")).toBeInTheDocument();
    expect(screen.getByText("fp-dl")).toBeInTheDocument();
    expect(screen.getByText("305")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    // Grouped rows for both families, pre-sorted by model_id.
    const table = await screen.findByRole("table");
    expect(within(table).getAllByText("mlp").length).toBeGreaterThan(0);
    expect(within(table).getByText("lstm")).toBeInTheDocument();
    expect(within(table).getByText("0.12")).toBeInTheDocument();
    expect(table.textContent?.indexOf("mlp")).toBeLessThan(table.textContent!.indexOf("lstm"));
  });

  it("refetches snapshot and metrics when the lottery selection changes (R2-S2)", async () => {
    selectLottery();
    render(<DL />);
    await screen.findByRole("table");
    useLotteryStore.setState({ selectedLotteryId: 2, selectedLotteryCode: "L2" });
    await waitFor(() => expect(modelsCalls).toBeGreaterThanOrEqual(2));
    await waitFor(() => expect(metricsCalls).toBeGreaterThanOrEqual(2));
    expect(lastModelsUrl).toContain("lottery_id=2");
    expect(lastMetricsUrl).toContain("lottery_id=2");
  });

  it("prompts to select a lottery with zero API calls and a disabled Train button (parity bonus)", async () => {
    render(<DL />);
    expect(await screen.findByText(/select a lottery/i)).toBeInTheDocument();
    expect(modelsCalls).toBe(0);
    expect(metricsCalls).toBe(0);
    expect(trainCalls).toBe(0);
    expect(screen.getByRole("button", { name: /^train$/i })).toBeDisabled();
  });

  it("renders the empty-state Train CTA on 404 SNAPSHOT_NOT_FOUND, not an error (R3-S1)", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/dl/models", () => err("no active snapshot", 404, "SNAPSHOT_NOT_FOUND")),
      http.get("*/api/v1/dl/metrics", () => env([]))
    );
    render(<DL />);

    expect(await screen.findByText(/no models trained yet/i)).toBeInTheDocument();
    const trainButtons = screen.getAllByRole("button", { name: /^train$/i });
    expect(trainButtons.length).toBeGreaterThan(0);
    for (const button of trainButtons) {
      expect(button).toBeEnabled();
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps an unrelated 404 as an error with retry (R3-S2)", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/dl/models", () => err("unknown lottery", 404, "RESOURCE_NOT_FOUND"))
    );
    render(<DL />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows the skeleton while models load, then the table replaces it (R6-S1)", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/dl/models", async () => {
        await delay(100);
        return env(snapshot);
      })
    );
    const { container } = render(<DL />);

    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await screen.findByRole("table");
    expect(container.querySelector(".animate-pulse")).toBeNull();
  });

  it("recovers to the data view after a failed fetch is retried (R6-S2)", async () => {
    selectLottery();
    let failing = true;
    server.use(
      http.get("*/api/v1/dl/models", () => (failing ? err("backend down") : env(snapshot)))
    );
    render(<DL />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    failing = false;
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await screen.findByRole("table");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("holds the busy state through a slow train and refetches on success (R4-S1)", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/dl/train", async () => {
        await delay(100);
        return env(trainResult);
      })
    );
    render(<DL />);
    await screen.findByRole("table");
    const modelsBefore = modelsCalls;
    const metricsBefore = metricsCalls;

    fireEvent.click(screen.getByRole("button", { name: /^train$/i }));

    const trainingButton = await screen.findByRole("button", {
      name: /training/i,
    });
    expect(trainingButton).toBeDisabled();
    expect(trainingButton).toHaveAttribute("aria-busy", "true");

    await waitFor(() => expect(modelsCalls).toBe(modelsBefore + 1));
    await waitFor(() => expect(metricsCalls).toBe(metricsBefore + 1));

    const settled = screen.getByRole("button", { name: /^train$/i });
    expect(settled).toBeEnabled();
  });

  it("surfaces a failed family row's error text from a 200 train response (R4-S2)", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/dl/train", () =>
        env({
          lottery_id: 1,
          results: [
            {
              family: "mlp",
              status: "active",
              snapshot_id: 7,
              fingerprint: "fp-dl",
              metrics_checksum: "cs1",
              error: null,
            },
            { family: "lstm", status: "failed", error: "no active F4 snapshot" },
          ],
        })
      )
    );
    render(<DL />);
    await screen.findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: /^train$/i }));

    expect(await screen.findByText(/lstm: no active F4 snapshot/i)).toBeInTheDocument();
  });

  it("renders an ErrorState when training rejects and Retry re-issues the POST (R4-S3)", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/dl/train", () => {
        trainCalls += 1;
        return err("training failed");
      })
    );
    render(<DL />);
    await screen.findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: /^train$/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(trainCalls).toBe(1);

    server.use(
      http.post("*/api/v1/dl/train", () => {
        trainCalls += 1;
        return env(trainResult);
      })
    );
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(trainCalls).toBe(2));
  });
});
