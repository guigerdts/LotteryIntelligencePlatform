import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";

/**
 * E2E core cycle (TEST-005, D3): create lottery → import draws → generate
 * statistics → dashboard. Scope guard: NO AI Assistant (IA) flow — the spec
 * only exercises `/estadisticas` and `/` (T-S6-03).
 *
 * Seeding uses the Playwright `request` fixture against the real backend
 * (:8000) because no create-lottery / import-draws UI page exists (D3). The
 * draws import endpoint reads a server-side file, so the CSV is written to a
 * temp path this test process (same host as uvicorn) can resolve, and the
 * absolute path is posted as `source_file`.
 */
const API_BASE = "http://localhost:8000/api/v1";

const LOTTERY_PAYLOAD = {
  code: "e2e",
  name: "E2E Test Lotto",
  country: "ES",
  min_number: 1,
  max_number: 45,
  numbers_to_select: 5,
};

/** Ten draws; draw 10 (top of the desc list) = 1 - 6 - 11 - 16 - 21. */
const DRAW_ROWS: Array<[number, string, number[], string, string]> = [
  [1, "2026-01-05", [1, 2, 3, 4, 5], "1000000", "10"],
  [2, "2026-01-12", [6, 7, 8, 9, 10], "900000", "9"],
  [3, "2026-01-19", [11, 12, 13, 14, 15], "800000", "8"],
  [4, "2026-01-26", [16, 17, 18, 19, 20], "700000", "7"],
  [5, "2026-02-02", [21, 22, 23, 24, 25], "600000", "6"],
  [6, "2026-02-09", [26, 27, 28, 29, 30], "500000", "5"],
  [7, "2026-02-16", [31, 32, 33, 34, 35], "400000", "4"],
  [8, "2026-02-23", [36, 37, 38, 39, 40], "300000", "3"],
  [9, "2026-03-02", [41, 42, 43, 44, 45], "200000", "2"],
  [10, "2026-03-09", [1, 6, 11, 16, 21], "100000", "1"],
];

/** POST /api/v1/lotteries — create the lottery the cycle revolves around. */
async function seedLottery(request: APIRequestContext) {
  const response = await request.post(`${API_BASE}/lotteries`, {
    data: LOTTERY_PAYLOAD,
  });
  expect(response.status(), "create lottery must return 201").toBe(201);
  const body = await response.json();
  expect(body.success).toBe(true);
  return body.data as { id: number; code: string };
}

/** POST /api/v1/draws/import — CSV written to a temp path, server-side read. */
async function seedDraws(request: APIRequestContext, lotteryCode: string) {
  const dir = mkdtempSync(join(tmpdir(), "lip-e2e-seed-"));
  const csvPath = join(dir, "seed.csv");
  const header = "draw_number,draw_date,numbers,super_number,jackpot,winners";
  const rows = DRAW_ROWS.map(([drawNumber, drawDate, numbers, jackpot, winners]) =>
    [drawNumber, drawDate, `"${numbers.join(",")}"`, "", jackpot, winners].join(",")
  );
  writeFileSync(csvPath, [header, ...rows].join("\n") + "\n", "utf8");
  try {
    const response = await request.post(`${API_BASE}/draws/import`, {
      data: { lottery_code: lotteryCode, source_file: csvPath },
    });
    expect(response.status(), "draws import must return 200").toBe(200);
    const body = await response.json();
    expect(body.success).toBe(true);
    expect(body.data.imported_rows).toBe(DRAW_ROWS.length);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("core cycle: seed → statistics snapshot → dashboard (TEST-005, D3)", async ({
  page,
  request,
}) => {
  // --- API seed (no create/import UI exists) ------------------------------
  const lottery = await seedLottery(request);
  await seedDraws(request, lottery.code);

  // --- Home: select the seeded lottery, draws render -----------------------
  await page.goto("/");
  // Selector loads lotteries asynchronously; `<option>` elements are never
  // "visible" to Playwright, so wait for the option to exist, then select it.
  await expect(page.locator(`#lottery-select option[value="${lottery.id}"]`)).toHaveCount(1);
  await page.selectOption("#lottery-select", String(lottery.id));

  // Latest draws table renders the newest draw first (desc order).
  await expect(page.locator("tbody")).toContainText("1 - 6 - 11 - 16 - 21");

  // --- Statistics: generate snapshot → charts render -----------------------
  await page.goto("/estadisticas");
  await page.getByRole("button", { name: "Generate Snapshot" }).click();
  await expect(page.getByRole("img", { name: "Frequency distribution per number" })).toBeVisible();
  await expect(page.locator(".recharts-responsive-container")).toBeVisible();
  await expect(page.getByText(/Snapshot #\d+/)).toBeVisible();

  // --- Home: dashboard renders draws + frequencies from the snapshot --------
  await page.goto("/");
  await expect(page.locator("tbody")).toContainText("1 - 6 - 11 - 16 - 21");
  await expect(page.getByRole("heading", { name: "Frequency summary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Most frequent" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Least frequent" })).toBeVisible();
  // 1 and 6 each appear in two seeded draws → top frequency count is 2×.
  await expect(page.locator("ol").first()).toContainText("2×");
  // Frontend ↔ backend connectivity is proven by the System health block.
  await expect(page.getByText("API status", { exact: true })).toBeVisible();
  await expect(page.locator("dl")).toContainText("ok");
});
