import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    // Release-candidate stability (F19 S1): lazy-route chunks + 21 jsdom
    // environments contend for CPU when files run in parallel on modest
    // hardware, starving findBy windows and producing run-to-run flaky
    // victims. Files now run sequentially and wait budgets are explicit;
    // assertions themselves are unchanged.
    fileParallelism: false,
    testTimeout: 20000,
    hookTimeout: 20000,
    // The Playwright E2E suite lives in e2e/; keep it out of vitest's default
    // **/*.{test,spec}.* discovery (TEST-005, slice S6).
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary", "html"],
      include: ["src/**"],
    },
  },
});
