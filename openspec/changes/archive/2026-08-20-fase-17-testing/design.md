# Design: Fase 17 — Testing

## Technical Approach

Fix-and-measure (approved exploration approach): P0 repairs the F16 S7 fixture regression first, then coverage is instrumented, CI (GitHub Actions) runs sharded report-only, E2E covers the core cycle, and a custom perf harness closes the phase. Maps to TEST-001..006; respects D1–D5.

## Architecture Decisions

| # | Decision | Options | Tradeoff | Choice |
|---|----------|---------|----------|--------|
| ADR-1 | P0 repair | (a) rename module fixtures; (b) reuse root `db`; (c) make root `migrated_db` function-scoped | (a) preserves each module's own engine/session semantics, zero behavior change; (b) changes semantics — modules exercise raw commit/rollback + N+1 counting that the savepoint model may alter; (c) destroys S7 per-test cost win (~3 s/test) | (a) rename |
| ADR-2 | DB strategy | session-scoped DB + savepoints vs per-test alembic migration | S7 validated ms/test isolation; per-test migrations make the >15 min suite worse | Keep S7 conftest unchanged |
| ADR-3 | Coverage gate | hard fail vs report-only + 3-run history | Hard gate fails on a distorted pre-baseline; artifact history enables D1 exactly | Report-only; `coverage-history.json` artifact; hard flag after 3 consecutive qualifying runs |
| ADR-4 | CI provider | GitHub Actions vs pre-commit | GHA = main gate on every push, zero infra (D5); pre-commit is local-only | GitHub Actions |
| ADR-5 | E2E stack | Playwright vs Cypress vs API-only | Playwright is JS-native to React/Vite, has `webServer` lifecycle + `request` API for seeding (D3) | Playwright |
| ADR-6 | Perf harness | pytest-benchmark vs custom | pytest-benchmark banned (D4); custom = N repeats + JSON + baseline/tolerance/outliers | Custom harness, non-PR workflow |
| ADR-7 | Suite sharding | single job vs per-dir matrix + combine | ~1 GB/>15 min single job OOMs; per-shard `COVERAGE_FILE` + `coverage combine` yields the full-suite number | 6-shard matrix + finalize job |

## P0 Fixture Repair (TEST-001)

Root `backend/tests/conftest.py` (lines 66–131) owns session-scoped `migrated_db`/`api_engine`/`connection`/`session_factory` plus autouse `_reset_outer_transaction`. Three modules shadow `migrated_db` function-scoped (`test_services.py:43`, `test_integrity.py:42`, `test_import_service.py:46`); the session-scoped `api_engine` then resolves the function-scoped name → `ScopeMismatch` ×63.

**Fix**: rename module fixtures `migrated_db → service_db / repo_db / import_db` (their `engine`/`session`/`db` chains follow). The autouse chain resolves the session fixture; modules keep fresh per-test tmp DBs, so N+1 counters (`test_integrity.py:69`) and raw commit/rollback paths are unchanged. No production change. **Verify**: 3 modules green alone, then the full backend suite via CI shards; non-S7 failures reported separately.

## Sequence Diagrams (config rules.design)

**CI coverage flow** (ADR-3/7):

    push ─▶ backend matrix (6 shards, COVERAGE_FILE=.coverage.<s>)
             │  each: pytest --cov=backend.app
             ▼
         coverage-finalize: combine ─▶ report ─▶ backend %
    push ─▶ frontend job: vitest run --coverage ─▶ frontend %
             ▼
         gate job: download coverage-history.json (allow missing)
           append {run_id, backend%, frontend%}
           last 3 runs ≥80 & ≥70 ─▶ hard_gate=true
           upload history + reports ─▶ job summary (never fails during establishment)

**E2E core cycle** (ADR-5, D3):

    Playwright webServer ─▶ uvicorn backend.app.main:app (seeded tmp DB, :8000)
                         ─▶ vite dev (:5173)
    test: request POST /api/v1/lotteries      (create — no create UI page exists)
        → request POST /api/v1/draws/import   (CSV seed — no import UI page exists)
        → UI /estadisticas → "Generate snapshot" → assert charts render
        → UI / (Home) → assert latest draws + frequencies render

**Perf harness** (ADR-6):

    run_harness.py ─▶ for op in config.yaml: warmup + 5 repeats
        ─▶ report-<ts>.json {mean, median, p95, std, outliers,
                             pass/fail vs baseline ± tolerance}
        ─▶ artifact (workflow_dispatch + schedule; not a PR gate)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/tests/test_services.py` | Modify | Rename shadowing `migrated_db` fixture |
| `backend/tests/test_integrity.py` | Modify | Same (P0) |
| `backend/tests/test_import_service.py` | Modify | Same (P0) |
| `backend/pyproject.toml` | Modify | Add `pytest-cov` dep; `[tool.coverage]` |
| `frontend/package.json` | Modify | Add `@vitest/coverage-v8`, `@playwright/test` |
| `frontend/vite.config.ts` | Modify | `coverage` block (v8, `src/**`, json-summary) |
| `.github/workflows/ci.yml` | Create | Backend matrix + finalize + frontend + gate |
| `.github/workflows/performance.yml` | Create | Manual/scheduled perf run |
| `frontend/playwright.config.ts` | Create | `webServer` boot of backend+frontend |
| `frontend/e2e/core-cycle.spec.ts` | Create | Core cycle test + seed helpers |
| `backend/tests/performance/harness.py` | Create | Measurement runner |
| `backend/tests/performance/config.yaml` | Create | Ops, runs, baselines, tolerances |
| `openspec/config.yaml` | Modify | `testing.coverage/e2e: true` at end; threshold stays 0 |

## Interfaces / Contracts

- Coverage: `[tool.coverage.run] source=["backend.app"]`; report `show_missing=true`, **no `fail_under`** (report-only; CI script evaluates).
- Frontend: `coverage: { provider: "v8", reporter: ["text","json-summary","html"], include: ["src/**"] }`.
- Perf JSON: `{op, unit, samples[], mean, p95, baseline, tolerance, pass}`.
- History artifact: `{runs: [{run_id, backend_pct, frontend_pct, passed}], hard_gate: bool}`.

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Integration (P0) | 63 repaired tests | Renamed fixtures; module + full-suite green |
| Frontend | 3 failing tests | History: raise pagination `waitFor` timeout; Networks: await lazy graph canvas; 3rd: diagnose msw/async race at apply |
| E2E | Core cycle only (D3) | Playwright, API-seeded, UI-driven stats + dashboard |
| Coverage | ≥80/≥70 | Report-only; hard gate after 3 consecutive runs |
| Perf | cold start (~5.6 s), cached stats GET, parallel bt/train | N=5, ±20% tolerance, JSON report |

## Threat Matrix

`references/threat-matrix.md` does not exist in this repo (verified by glob). Rows: routing — N/A (no new routes); shell commands — N/A (CI steps are declarative YAML); subprocess/process integration — **Applicable**: Playwright `webServer` spawns uvicorn + vite; safe/failure behavior = healthcheck + `reuseExistingServer:false` + job timeout; RED test = the E2E spec; VCS/PR automation — N/A; executable-file classification — N/A.

## Migration / Rollout

No data migration. Rollout = stacked-to-main PR slices (≤400 lines): P0 → instrumentation → CI → E2E → perf. Config flags flipped in the final slice.

## Open Questions

- None blocking. Artifact-based 3-run history is best-effort (concurrent runs/purged artifacts reset the streak) — accepted for D1; a history branch is the deferred alternative.