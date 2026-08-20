import { fileURLToPath } from "node:url";
import path from "node:path";
import { defineConfig } from "@playwright/test";

// Frontend lives at <repo>/frontend; backend at <repo>/backend. The config file
// is ESM ("type": "module"), so derive dirs from import.meta.url (no __dirname).
const FRONTEND_DIR = path.dirname(fileURLToPath(import.meta.url));
const BACKEND_DIR = path.resolve(FRONTEND_DIR, "..", "backend");

/**
 * E2E core-cycle suite (TEST-005, ADR-5).
 *
 * Boots BOTH real servers before any test:
 *   (a) uvicorn serving `backend.app.main:create_app` on :8000 against a
 *       throwaway SQLite DB freshly migrated with `alembic upgrade head`
 *       (env.py falls back to `LIP_DATABASE_URL`), and
 *   (b) `vite dev` on :5173 pointed at that backend via `VITE_API_BASE_URL`
 *       (no vite proxy exists; the backend CORS allow-list already accepts
 *       http://localhost:5173).
 *
 * Subprocess RED guard (threat matrix): each server either fails fast
 * (migration/import error, `--strictPort` port conflict) or the readiness
 * healthcheck poll times out (`webServer.timeout`) — the suite can never hang
 * on a half-booted server. `reuseExistingServer: false` guarantees the E2E
 * run always exercises a fresh backend + DB, never a stale local process.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "e2e-results",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      // Migrate a fresh tmp DB, then serve the API from it on :8000.
      command:
        'DB=$(mktemp /tmp/lip-e2e-db-XXXXXX.db) && ' +
        'LIP_DATABASE_URL="sqlite:///$DB" .venv/bin/python -m alembic upgrade head && ' +
        'LIP_DATABASE_URL="sqlite:///$DB" .venv/bin/uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000',
      cwd: BACKEND_DIR,
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // Dev server on :5173; strictPort fails fast instead of silently moving
      // to another port (which would make the readiness poll hang).
      command: "npm run dev -- --host 127.0.0.1 --strictPort",
      cwd: FRONTEND_DIR,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 60_000,
      env: { ...process.env, VITE_API_BASE_URL: "http://localhost:8000/api/v1" },
    },
  ],
});