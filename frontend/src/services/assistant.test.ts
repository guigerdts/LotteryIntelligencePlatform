import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { NotFoundError, ServerError } from "./api";
import {
  assist,
  explainAssistant,
  interpretAssistant,
  reportAssistant,
  summarizeAssistant,
} from "./assistant";

const env = (data: unknown) =>
  HttpResponse.json({ success: true, data, timestamp: "2026-01-01T00:00:00Z" });

const response = {
  text: "Texto en español.",
  engine_version: "1.0.0",
  fingerprint: "fp-1",
};

let lastUrl = "";
let lastBody: unknown = null;

const server = setupServer(
  http.get("*/api/v1/assistant/explain", ({ request }) => {
    lastUrl = request.url;
    return env(response);
  }),
  http.get("*/api/v1/assistant/interpret", ({ request }) => {
    lastUrl = request.url;
    return env(response);
  }),
  http.get("*/api/v1/assistant/report", ({ request }) => {
    lastUrl = request.url;
    return env(response);
  }),
  http.post("*/api/v1/assistant/summarize", async ({ request }) => {
    lastUrl = request.url;
    lastBody = await request.json();
    return env(response);
  }),
  http.post("*/api/v1/assistant/assist", async ({ request }) => {
    lastUrl = request.url;
    lastBody = await request.json();
    return env(response);
  })
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  lastUrl = "";
  lastBody = null;
});
afterAll(() => server.close());

describe("assistant service", () => {
  it("explain sends lottery_code and optional subject/context params", async () => {
    const result = await explainAssistant("L1", "5", "last 10 draws");
    expect(result).toEqual(response);
    expect(lastUrl).toContain("/assistant/explain?lottery_code=L1");
    expect(lastUrl).toContain("subject=5");
    expect(lastUrl).toContain("context=last+10+draws");
  });

  it("interpret sends only lottery_code and unwraps the envelope", async () => {
    const result = await interpretAssistant("L1");
    expect(result).toEqual(response);
    expect(lastUrl).toContain("/assistant/interpret?lottery_code=L1");
  });

  it("report appends scope only when provided", async () => {
    await reportAssistant("L1", "probability");
    expect(lastUrl).toContain("/assistant/report?lottery_code=L1");
    expect(lastUrl).toContain("scope=probability");
    await reportAssistant("L1");
    const url = new URL(lastUrl);
    expect(url.pathname).toBe("/api/v1/assistant/report");
    expect(url.search).toBe("?lottery_code=L1");
  });

  it("summarize posts the experiment_id and optional run_ids", async () => {
    const result = await summarizeAssistant({ experiment_id: 2, run_ids: [1, 3] });
    expect(result).toEqual(response);
    expect(lastBody).toEqual({ experiment_id: 2, run_ids: [1, 3] });
  });

  it("assist posts question and lottery_code", async () => {
    const result = await assist("¿Qué significa?", "L1");
    expect(result).toEqual(response);
    expect(lastBody).toEqual({ question: "¿Qué significa?", lottery_code: "L1" });
  });

  it("maps a 404 error envelope to NotFoundError", async () => {
    server.use(
      http.get("*/api/v1/assistant/explain", () =>
        HttpResponse.json(
          {
            success: false,
            error: { code: "RESOURCE_NOT_FOUND", message: "Lottery not found" },
            timestamp: "",
          },
          { status: 404 }
        )
      )
    );
    await expect(explainAssistant("L999")).rejects.toBeInstanceOf(NotFoundError);
  });

  it("maps a 500 error envelope to ServerError with the message", async () => {
    server.use(
      http.get("*/api/v1/assistant/report", () =>
        HttpResponse.json(
          {
            success: false,
            error: { code: "assistant_error", message: "Generation failed" },
            timestamp: "",
          },
          { status: 500 }
        )
      )
    );
    await expect(reportAssistant("L1")).rejects.toThrow("Generation failed");
    await expect(reportAssistant("L1")).rejects.toBeInstanceOf(ServerError);
  });
});
