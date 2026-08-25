import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import MisNumeros from "./MisNumeros";
import { runNumbersPipeline } from "../services/pipeline";
import { useLotteryStore } from "../store/useLotteryStore";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });
const err = (message: string, status = 500, code = "INTERNAL_ERROR") =>
  HttpResponse.json({ success: false, error: { code, message }, timestamp: "" }, { status });

/** Canonical stage order of POST /pipeline/numbers (R2/S2 contract). */
const STAGE_ORDER = ["stats", "features", "ml", "dl", "bt", "rank", "select", "gen"];

const combinations = [
  {
    position: 1,
    numbers: [3, 12, 19, 27, 41],
    super_number: 8,
    score: 0.123456,
  },
  {
    position: 2,
    numbers: [5, 9, 22, 30, 38],
    super_number: 14,
    score: 0.098765,
  },
];

const generationResult = {
  snapshot_id: 42,
  lottery_id: 1,
  selection_id: 5,
  version: "2.0.0",
  status: "active",
  fingerprint: "fp-gen-42",
  seed: 99,
  count: 5,
  combinations,
};

const okStages = () =>
  STAGE_ORDER.map((name) => ({
    name,
    status: "completed",
    snapshot_id: 10 + STAGE_ORDER.indexOf(name),
    fingerprint: `fp-${name}`,
    error_code: null,
    detail: "new artifact persisted",
  }));

const failedRankStages = () =>
  okStages().map((stage) =>
    stage.name === "rank"
      ? {
          ...stage,
          status: "failed",
          snapshot_id: null,
          fingerprint: null,
          error_code: "PIPE_STAGE_FAILED",
          detail: "ranking stale for backtest context after one rerank",
        }
      : stage
  );

let pipelineCalls = 0;
let otherApiCalls = 0;
let lastPipelineBody: Record<string, unknown> | null = null;

const server = setupServer(
  http.post("*/api/v1/pipeline/numbers", async ({ request }) => {
    pipelineCalls += 1;
    lastPipelineBody = (await request.json()) as Record<string, unknown>;
    return env({ stages: okStages(), result: generationResult });
  })
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

beforeAll(() => {
  server.listen();
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    if (url.pathname.endsWith("/api/v1/pipeline/numbers")) return;
    otherApiCalls += 1;
  });
});

afterEach(() => {
  server.resetHandlers();
  pipelineCalls = 0;
  otherApiCalls = 0;
  lastPipelineBody = null;
  localStorage.clear();
  useLotteryStore.setState({
    lotteries: [],
    selectedLotteryId: null,
    selectedLotteryCode: null,
    isLoading: false,
    error: null,
  });
});

afterAll(() => {
  server.events.removeAllListeners();
  server.close();
});

describe("runNumbersPipeline client", () => {
  it("POSTs to /api/v1/pipeline/numbers and unwraps the SuccessEnvelope", async () => {
    const result = await runNumbersPipeline({ lottery_id: 1, count: 5 });
    expect(result.stages).toHaveLength(8);
    expect(STAGE_ORDER).toEqual(result.stages.map((stage) => stage.name));
    expect(result.result?.snapshot_id).toBe(42);
    expect(lastPipelineBody).toEqual({ lottery_id: 1, count: 5 });
  });
});

describe("Mis Números page", () => {
  it("fires exactly ONE orchestrator request per CTA click and no stage endpoints (R1)", async () => {
    selectLottery();
    render(<MisNumeros />);

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));

    await screen.findByRole("table", { name: /generated combinations/i });
    await waitFor(() => expect(pipelineCalls).toBe(1));
    expect(otherApiCalls).toBe(0);
  });

  it("holds aria-busy through a slow call and Retry re-posts after a 500 (R1)", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/pipeline/numbers", async () => {
        pipelineCalls += 1;
        await delay(150);
        return err("pipeline failed", 502, "PIPE_STAGE_FAILED");
      })
    );
    render(<MisNumeros />);

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));

    const busyButton = await screen.findByRole("button", { name: /running/i });
    expect(busyButton).toBeDisabled();
    expect(busyButton).toHaveAttribute("aria-busy", "true");

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    server.use(
      http.post("*/api/v1/pipeline/numbers", () => {
        pipelineCalls += 1;
        lastPipelineBody = null;
        return env({ stages: okStages(), result: generationResult });
      })
    );
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await screen.findByRole("table", { name: /generated combinations/i });
    expect(pipelineCalls).toBe(2);
  });

  it("renders all eight stages in canonical order with their statuses (R2)", async () => {
    selectLottery();
    render(<MisNumeros />);

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));

    const report = await screen.findByRole("list", {
      name: /pipeline stages/i,
    });
    const text = report.textContent ?? "";
    for (let i = 0; i < STAGE_ORDER.length - 1; i++) {
      expect(text.indexOf(STAGE_ORDER[i] as string)).toBeLessThan(
        text.indexOf(STAGE_ORDER[i + 1] as string)
      );
    }
    for (const name of STAGE_ORDER) {
      expect(text).toContain(name);
    }
    expect(screen.getByRole("table", { name: /generated combinations/i })).toBeInTheDocument();
  });

  it("surfaces a failed rank stage without crashing and hides combinations (R2)", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/pipeline/numbers", () =>
        env({ stages: failedRankStages(), result: null })
      )
    );
    render(<MisNumeros />);

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));

    const report = await screen.findByRole("list", {
      name: /pipeline stages/i,
    });
    expect(report.textContent).toContain("failed");
    expect(screen.getByText(/PIPE_STAGE_FAILED/)).toBeInTheDocument();
    expect(
      screen.queryByRole("table", { name: /generated combinations/i })
    ).not.toBeInTheDocument();
    // Page stays interactive: CTA re-enabled and disclaimer still visible.
    expect(screen.getByRole("button", { name: /generate numbers/i })).toBeEnabled();
    expect(screen.getByText(/completamente aleatorios/i)).toBeInTheDocument();
  });

  it("labels every ticket as valid for both draws and offers no toggle (R3)", async () => {
    selectLottery();
    render(<MisNumeros />);

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));
    await screen.findByRole("table", { name: /generated combinations/i });

    expect(screen.getAllByText(/un boleto, dos sorteos/i)).not.toHaveLength(0);
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByText(/toggle/i)).not.toBeInTheDocument();
  });

  it("sends count=5 by default and keeps the control adjustable (R4)", async () => {
    selectLottery();
    render(<MisNumeros />);

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));
    await screen.findByRole("table", { name: /generated combinations/i });
    await waitFor(() => expect(pipelineCalls).toBe(1));
    expect(lastPipelineBody?.count).toBe(5);

    fireEvent.change(screen.getByLabelText(/count/i), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));
    await waitFor(() => expect(pipelineCalls).toBe(2));
    expect(lastPipelineBody?.count).toBe(3);
  });

  it("renders exactly the eight official prize tiers as a rules reference (R5)", async () => {
    selectLottery();
    render(<MisNumeros />);

    const table = await screen.findByRole("table", { name: /prize tiers/i });
    const rows = table.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(8);
    expect(table.textContent).toMatch(/5\s*\+\s*superbalota/i);
    expect(table.textContent).toMatch(/jackpot/i);
    expect(table.textContent).toMatch(/paramutual/i);
    expect(table.textContent).toMatch(/bet refund|refund/i);
  });

  it("keeps the randomness disclaimer visible idle and after generation (R6)", async () => {
    selectLottery();
    render(<MisNumeros />);

    expect(screen.getByText(/completamente aleatorios/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /generate numbers/i }));
    await screen.findByRole("table", { name: /generated combinations/i });

    expect(screen.getByText(/completamente aleatorios/i)).toBeInTheDocument();
    expect(screen.getByText(/aleatorios/i)).toBeInTheDocument();
  });

  it("prompts to select a lottery with a disabled CTA when none is chosen", async () => {
    render(<MisNumeros />);

    expect(await screen.findByText(/select a lottery/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate numbers/i })).toBeDisabled();
    expect(pipelineCalls).toBe(0);
  });
});
