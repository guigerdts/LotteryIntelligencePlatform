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
let explainCalls = 0;
let interpretCalls = 0;
let reportCalls = 0;
let summarizeCalls = 0;
let assistCalls = 0;
let lastAssistBody: { question: string; lottery_code: string } | null = null;

const assistantResponse = {
  text: "El número 5 muestra una frecuencia alta en los últimos sorteos.",
  engine_version: "1.0.0",
  fingerprint: "fp-abc123",
};

const server = setupServer(
  http.get("*/api/v1/health", () => env({ status: "ok" })),
  http.get("*/api/v1/version", () =>
    env({ version: "1.0.0", app: "Lottery Intelligence Platform" })
  ),
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
  http.get("*/api/v1/assistant/explain", () => {
    explainCalls += 1;
    return env(assistantResponse);
  }),
  http.get("*/api/v1/assistant/interpret", () => {
    interpretCalls += 1;
    return env(assistantResponse);
  }),
  http.get("*/api/v1/assistant/report", () => {
    reportCalls += 1;
    return env({ ...assistantResponse, text: "Informe de la lotería L1." });
  }),
  http.post("*/api/v1/assistant/summarize", () => {
    summarizeCalls += 1;
    return env({ ...assistantResponse, text: "Resumen del experimento." });
  }),
  http.post("*/api/v1/assistant/assist", async ({ request }) => {
    assistCalls += 1;
    lastAssistBody = (await request.json()) as {
      question: string;
      lottery_code: string;
    };
    return env({ ...assistantResponse, text: "Respuesta generada para tu pregunta." });
  })
);

const selectLottery = () =>
  useLotteryStore.setState({ selectedLotteryId: 1, selectedLotteryCode: "L1" });

const ask = (question: string) => {
  fireEvent.change(screen.getByLabelText(/haz una pregunta sobre esta lotería/i), {
    target: { value: question },
  });
  fireEvent.click(screen.getByRole("button", { name: "Preguntar" }));
};

const setExperiment = (id: string) =>
  fireEvent.change(screen.getByLabelText(/id del experimento/i), {
    target: { value: id },
  });

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  modelsCalls = 0;
  metricsCalls = 0;
  probCalls = 0;
  explainCalls = 0;
  interpretCalls = 0;
  reportCalls = 0;
  summarizeCalls = 0;
  assistCalls = 0;
  lastAssistBody = null;
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
    expect(
      await screen.findByRole("heading", { name: /asistente ia/i, level: 2 })
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Estado del sistema" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Estado del modelo" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Probabilidades recientes" })).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument();
    server.use(http.get("*/api/v1/ml/models", () => env(snapshot)));
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(screen.getByText("core-5")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows skeleton placeholders while sections load", async () => {
    selectLottery();
    server.use(
      http.get("*/api/v1/probability/L1/probabilities", () =>
        delay(50).then(() => env(probabilityList))
      )
    );
    const { container } = render(<IA />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("prompts to select a lottery and does not call lottery-scoped endpoints", async () => {
    render(<IA />);
    expect(
      (await screen.findAllByText(/selecciona una loter/i)).length
    ).toBeGreaterThan(0);
    expect(modelsCalls).toBe(0);
    expect(metricsCalls).toBe(0);
    expect(probCalls).toBe(0);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("sends the question to /assistant/assist and renders the Spanish text", async () => {
    selectLottery();
    render(<IA />);
    await screen.findByText("ok");
    ask("¿Por qué cambió la frecuencia?");
    await waitFor(() => expect(assistCalls).toBe(1));
    expect(lastAssistBody).toEqual({
      question: "¿Por qué cambió la frecuencia?",
      lottery_code: "L1",
    });
    expect(await screen.findByText("Respuesta generada para tu pregunta.")).toBeInTheDocument();
  });

  it("shows a skeleton while an assistant request is in flight", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/assistant/assist", async () => {
        assistCalls += 1;
        await delay(50);
        return env({ ...assistantResponse, text: "Respuesta lenta." });
      })
    );
    const { container } = render(<IA />);
    await screen.findByText("ok");
    ask("¿Qué significa?");
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    await waitFor(() => expect(container.querySelector(".animate-pulse")).toBeNull());
    expect(await screen.findByText("Respuesta lenta.")).toBeInTheDocument();
  });

  it("shows an error with retry for the assistant panel and recovers", async () => {
    selectLottery();
    server.use(http.post("*/api/v1/assistant/assist", () => err("Assistant error")));
    render(<IA />);
    await screen.findByText("ok");
    ask("¿Qué significa?");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/assistant error/i);
    server.use(
      http.post("*/api/v1/assistant/assist", async () =>
        env({ ...assistantResponse, text: "Recuperado." })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(screen.getByText("Recuperado.")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders empty-data Spanish text as content, not as an error", async () => {
    selectLottery();
    server.use(
      http.post("*/api/v1/assistant/assist", async () =>
        env({ ...assistantResponse, text: "No hay datos suficientes." })
      )
    );
    render(<IA />);
    await screen.findByText("ok");
    ask("Resume");
    expect(await screen.findByText("No hay datos suficientes.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("only calls the five assistant endpoints and existing status endpoints (NFR-2)", async () => {
    selectLottery();
    const allowed = new Set([
      "/api/v1/health",
      "/api/v1/version",
      "/api/v1/ml/models",
      "/api/v1/ml/metrics",
      "/api/v1/probability/L1/probabilities",
      "/api/v1/assistant/explain",
      "/api/v1/assistant/interpret",
      "/api/v1/assistant/report",
      "/api/v1/assistant/summarize",
      "/api/v1/assistant/assist",
    ]);
    const unexpected: string[] = [];
    const onRequest = ({ request }: { request: Request }) => {
      const path = new URL(request.url).pathname;
      if (!allowed.has(path)) unexpected.push(path);
    };
    server.events.on("request:start", onRequest);
    try {
      render(<IA />);
      await screen.findByText("ok");
      fireEvent.click(screen.getByRole("button", { name: "Explicar" }));
      fireEvent.click(screen.getByRole("button", { name: "Interpretar" }));
      fireEvent.click(screen.getByRole("button", { name: "Informe" }));
      setExperiment("2");
      fireEvent.click(screen.getByRole("button", { name: "Resumir" }));
      ask("Hola");
      await waitFor(() => {
        expect([explainCalls, interpretCalls, reportCalls, summarizeCalls, assistCalls]).toEqual([
          1, 1, 1, 1, 1,
        ]);
      });
      expect(unexpected).toEqual([]);
    } finally {
      server.events.removeListener("request:start", onRequest);
    }
  });
});
