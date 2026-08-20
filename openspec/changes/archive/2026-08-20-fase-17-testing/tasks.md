# Tasks: Fase 17 — Testing

Status: **archived** · Store: openspec · Date: 2026-08-19 · Archived: 2026-08-20
Canonical apply order: **S1 → S2 → S3 → S4 → S5 → S6** (each slice = one stacked-to-main PR, conventional commits `[T-Sx-yy]`, no AI attribution). S5/S6 are independent of each other after S4; proposal approach puts E2E last (design §Migration lists E2E→perf — see Risks). Planning only — no implementation, no commits/PRs (owner mandate). Backend suite >15 min / ~1 GB peak → full-suite verification runs per-directory, never one process.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1060 total (S1 70, S2 40, S3 350, S4 220, S5 175, S6 205) |
| 400-line budget risk | Medium per slice (S3 open-ended) / High total |
| Chained PRs recommended | Yes |
| Suggested split | 6 PRs, one per slice: S1 → S2 → S3 → S4 → S5 → S6 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main (owner pre-authorized) |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

**Split-on-overage rule:** if any slice's authored diff exceeds 400 additions+deletions at apply (`git diff --numstat`), split into chained PRs (S3 → S3a backend / S3b frontend). NO `size:exception`.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| S1 | P0 fixture repair + suite green (TEST-001) | PR 1 | `backend/.venv/bin/pytest tests/test_services.py tests/test_integrity.py tests/test_import_service.py -q` (63 green) + `npm test` | full backend suite per-directory (memory constraint) | revert fixture renames (test-only) |
| S2 | Coverage instrumentation + baseline (TEST-002) | PR 2 | `backend/.venv/bin/pytest --cov=backend.app <dir>` + `npx vitest run --coverage` | real coverage run; baseline recorded only after suite green | remove deps + coverage blocks |
| S3 | Gap-fill to ≥80/≥70 (TEST-002/003) | PR 3 | `backend/.venv/bin/pytest --cov=backend.app <touched dirs>` + `npx vitest run --coverage` | coverage delta vs S2 baseline report | revert test-only additions |
| S4 | CI main gate (TEST-004) | PR 4 | `backend/.venv/bin/ruff check .` + per-shard pytest (CI executes) | first pushed GitHub Actions run (6 shards + frontend + gate) | delete `.github/workflows/` |
| S5 | Perf harness (TEST-006) | PR 5 | `backend/.venv/bin/python tests/performance/harness.py --config tests/performance/config.yaml` | real harness run → `report-<ts>.json` + outlier flags | delete `backend/tests/performance/` |
| S6 | E2E core cycle (TEST-005) | PR 6 | `npx playwright test` (frontend) | Playwright `webServer` boots uvicorn+vite; real core cycle | delete `frontend/e2e/` + playwright.config.ts + revert config flags |

## Slice S1 — P0 fixture regression repair [~70 ln] (TEST-001)

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S1-01 | TEST-001 | [x] Rename shadowing fixture `migrated_db → service_db` (line 44) + `engine`/`session` chain (54-62); keep function scope + per-test tmp DB | modify `backend/tests/test_services.py` | ADR-1 (rename preserves module semantics); GF-1: N/A — behavior-preserving, no computation change | 10 |
| T-S1-02 | TEST-001 | [x] Same rename `migrated_db → repo_db` (line 43; chain 53-61); N+1 counters (line 69) untouched | modify `backend/tests/test_integrity.py` | never skip/xfail/hide (scenario 2); root autouse chain resolves session fixture | 8 |
| T-S1-03 | TEST-001 | [x] Same rename `migrated_db → import_db` (line 47; chain 57-59) | modify `backend/tests/test_import_service.py` | modules keep fresh per-test tmp DBs | 6 |
| T-S1-04 | TEST-001 | [x] Gate: 3 modules 63/63 green, none skipped; then full backend suite per-directory green | — | non-S7 failures reported separately, not folded into P0 (scenario 3); no production change | 15 |
| T-S1-05 | TEST-001 | [x] Fix 3 failing frontend tests: History.test.tsx pagination `waitFor` timeout; Networks.test.tsx await lazy graph canvas; diagnose/fix 3rd (msw/async race) at apply | modify `frontend/src/pages/History.test.tsx`, `frontend/src/pages/Networks.test.tsx` (+1 TBD at apply) | gate: `npm test` green; ruff on backend touched files | 30 |

## Slice S2 — Coverage instrumentation + baseline [~40 ln] (TEST-002)

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S2-01 | TEST-002 | [x] Add `pytest-cov` dep + `[tool.coverage.run] source=["backend.app"]`; `[tool.coverage.report] show_missing=true`, NO `fail_under` | modify `backend/pyproject.toml` | report-only (ADR-3); CI script evaluates, coverage never fails | 12 |
| T-S2-02 | TEST-002 | [x] Add `@vitest/coverage-v8` dev dep + `coverage: { provider: "v8", reporter: ["text","json-summary","html"], include: ["src/**"] }` | modify `frontend/package.json`, `frontend/vite.config.ts` | json-summary feeds the S4 gate job | 12 |
| T-S2-03 | TEST-002 | [x] Gate + baseline: full backend suite green per-directory FIRST (TEST-002 contract), then `pytest --cov=backend.app` per dir + `npx vitest run --coverage`; record backend%/frontend% into `coverage-history.json` `{runs:[{run_id,backend_pct,frontend_pct,passed}],hard_gate:false}` (path resolved at apply per ADR-3) | create `coverage-history.json` (repo path) | baseline only after green suite; rollback = revert S2-01/02 | 16 |

## Slice S3 — Gap-filling toward targets [~350 ln] (TEST-002/003)

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S3-01 | TEST-002/003 | [x] Measure per-module coverage of `backend/src/backend/app/services/` (17 modules); list top uncovered modules to target | — | per-module report saved (`/tmp/opencode/coverage-s3.json`); drives T-S3-02 targets | 10 |
| T-S3-02 | TEST-002/003 | [x] Add backend tests for top uncovered service modules in existing per-domain dirs (meta orchestration in `tests/meta/test_meta_service.py`; exp metric readers in new `tests/test_exp_metric_readers.py`) | modify/create `backend/tests/**` | RED-first (strict TDD, config.yaml); meta_service 50→78%, exp_service 78→98%; 3 real defects documented, not masked | 200 |
| T-S3-03 | TEST-002/003 | [x] Add frontend tests for uncovered components (ComingSoon, DataTable branches, Sidebar matchMedia) | create `frontend/src/components/*.test.tsx` | ComingSoon 0→100%, Sidebar funcs 50→100%, DataTable branches 81.39→91.83%; frontend total 94.59→95.22% | 130 |
| T-S3-04 | TEST-002/003 | [x] Gate: `pytest --cov=backend.app` touched dirs + `npx vitest run --coverage`; record delta vs S2 baseline; diff >400 → split S3a/S3b (split-on-overage) | — | ruff touched dirs; rollback = revert test-only additions | 10 |

## Slice S4 — CI main gate (GitHub Actions) [~220 ln] (TEST-004)

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S4-01 | TEST-004, ADR-7 | [x] Create `ci.yml`: backend matrix of 6 shards (balanced root+12 dirs; `COVERAGE_FILE=.coverage.<s>`, `pytest --cov=backend.app`); `coverage-finalize` job (combine → report → backend %); frontend job (`vitest run --coverage`); gate job (download history allow-missing, append run, last-3 runs ≥80/≥70 → `hard_gate=true`, upload history+reports, summary only — never fails during establishment) | create `.github/workflows/ci.yml` | TEST-003 scenarios 1-2; D1: hard gate only after 3 consecutive qualifying runs | 170 |
| T-S4-02 | TEST-004, D5 | [x] pre-commit stays complementary — no gate logic added; CI is the gate (scenario 3: bypassing hooks still gated) | modify `.pre-commit-config.yaml` (comment only, if touched) | — | 5 |
| T-S4-03 | TEST-004, ADR-6 | [x] Create `performance.yml`: `workflow_dispatch` + `schedule`; runs S5 harness; uploads report artifact; NOT a PR gate | create `.github/workflows/performance.yml` | perf runs manual/scheduled only | 35 |
| T-S4-04 | TEST-004 | [x] Gate: YAML/actionlint syntax valid; first pushed CI run green (shards + frontend + gate pass, report-only); numstat 435 > 400 → split into S4a (#55) + S4b (#56), both merged | — | rollback = delete workflow files | 10 |

## Slice S5 — Performance harness [~175 ln] (TEST-006)

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S5-01 | TEST-006, ADR-6 | [x] Create `harness.py`: per-op warmup + N=5 repeats; mean/median/p95/std/outliers; pass/fail vs baseline ± tolerance; writes `report-<ts>.json` `{op, unit, samples[], mean, p95, baseline, tolerance, pass}` | create `backend/tests/performance/harness.py` | custom harness, NOT pytest-benchmark (D4) | 140 |
| T-S5-02 | TEST-006 | [x] Create `config.yaml`: ops = cold start (~5.6 s baseline), cached statistics GET, parallel bt/train; runs: 5; tolerance: ±20% | create `backend/tests/performance/config.yaml` | ops per design Testing Strategy | 30 |
| T-S5-03 | TEST-006 | [x] Gate: harness run → valid JSON with variance + outlier flags; grep confirms pytest-benchmark absent from pyproject/lockfiles (scenario 2) | — | functional timing tests (`--durations`) are NOT benchmarks | 5 |

## Slice S6 — E2E core cycle (Playwright) [~205 ln] (TEST-005) + config flip

| ID | Scope | Description | Files | Notes | Lines |
|----|-------|-------------|-------|-------|-------|
| T-S6-01 | TEST-005, ADR-5 | [x] Create `playwright.config.ts`: `webServer` boots uvicorn `backend.app.main:app` (seeded tmp DB, :8000) + `vite dev` (:5173); HTTP readiness healthcheck; `reuseExistingServer:false`; CI job timeout (threat-matrix subprocess row: safe failure = healthcheck/timeout, never hang) | create `frontend/playwright.config.ts` | subprocess RED guard = T-S6-02 spec | 60 |
| T-S6-02 | TEST-005, D3 | [x] Create `core-cycle.spec.ts`: API-seed `POST /api/v1/lotteries` + `POST /api/v1/draws/import` (CSV) via Playwright `request` (no create/import UI exists); UI `/estadisticas` → "Generate snapshot" → charts render; `/` Home → draws + frequencies render | create `frontend/e2e/core-cycle.spec.ts` | RED first: spec fails until seed helpers land; both work in the same slice so it must end GREEN | 130 |
| T-S6-03 | TEST-005 | [x] Negative scope check: no AI Assistant (IA) flow spec/page added (scenario 2) | — | scope guard | 5 |
| T-S6-04 | TEST-005 | [x] Final slice: flip `openspec/config.yaml` `testing.coverage: true`, `testing.e2e: true`; threshold stays 0 (D1) | modify `openspec/config.yaml` | gate: `npx playwright test` green; `npm test` + backend suite unaffected | 10 |

## Dependency Graph + Apply Order

```
S1 (P0 repair) → S2 (instrument + baseline) → S3 (gap-fill) → S4 (CI) → S5 (perf) → S6 (E2E)
```
S5/S6 independent of each other after S4 (no cross-dependency); proposal approach = E2E last. Any edge broken (e.g. S2 baseline before S1 green) blocks the slice.

## Verification / Gates Strategy (per slice)

- **Lint**: `backend/.venv/bin/ruff check` + `ruff format` on touched dirs (S1-S3, S5).
- **pytest**: `backend/.venv/bin/pytest <affected dirs>`; full suite ALWAYS per-directory (1 GB peak; OOM is a limit, not a defect — conftest.py docstring).
- **numstat ≤400**: per PR `git diff --numstat`; overage → split into chained PRs, no `size:exception`.
- **GF-1**: N/A across F17 — no engine/computation changes; S1 behavior-preserving by construction (63 tests pass unchanged, none skipped).
- **Spec mapping**: S1→TEST-001 (1-3), S2→TEST-002 (1-2), S3→TEST-002/003 (1), S4→TEST-004 (1-3), S5→TEST-006 (1-2), S6→TEST-005 (1-2). Threat-matrix rows routing/shell/VCS/executable = N/A (design verified; no new routes, YAML is declarative); subprocess row covered by T-S6-01/02.

## Risks

- **Design-internal ordering inconsistency (flagged, resolved):** design §Migration/Rollout lists "P0 → instrumentation → CI → E2E → perf", while the approved proposal approach says "E2E last" (perf at 5, E2E at 6). S5/S6 share no dependency → followed proposal + orchestrator order (S5 → S6); reversible at apply without impact.
- S3 gap-filling is open-ended (~350 ln planned) → split-on-overage into S3a/S3b; targets set by T-S3-01 measurement, not guesses.
- 3-run coverage history is best-effort (design Open Question: concurrent runs/purged artifacts reset the streak) — accepted for D1.
- 3rd failing frontend test root-caused at apply (design defers: msw/async race).
- New dev deps: pytest-cov, @vitest/coverage-v8, @playwright/test (proposal risk — recorded).

## Next Recommended

None — change archived 2026-08-20. All slices S1-S6 merged to main (PRs #49-#58) plus config flip 06879fc; SDD cycle complete.

## Skill Resolution

paths-injected — sdd-tasks + `_shared/sdd-phase-common.md` + `_shared/openspec-convention.md`; chained-pr + work-unit-commits patterns applied from the F16 tasks.md precedent.

## Progress (machine-readable checkboxes)

- [x] T-S1-01 fixture rename test_services (migrated_db → service_db)
- [x] T-S1-02 fixture rename test_integrity (migrated_db → repo_db)
- [x] T-S1-03 fixture rename test_import_service (migrated_db → import_db)
- [x] T-S1-04 gate: 3 modules 63/63 green + full backend suite per-directory
- [x] T-S1-05 frontend flakes fixed (History/Networks waits)
- [x] T-S2-01 pytest-cov + [tool.coverage] (no fail_under)
- [x] T-S2-02 @vitest/coverage-v8 + coverage block
- [x] T-S2-03 gate + baseline (backend 90.05%, frontend 94.59%)
- [x] T-S3-01 per-module coverage measurement
- [x] T-S3-02 backend gap-fill meta/exp + 4 production defects fixed
- [x] T-S3-03 frontend gap-fill (ComingSoon/Sidebar/DataTable)
- [x] T-S3-04 gate + delta vs S2 (backend 91.88%, frontend 95.22%)
- [x] T-S4-01 ci.yml 6-shard matrix + coverage gate (report-only)
- [x] T-S4-02 pre-commit stays complementary
- [x] T-S4-03 performance.yml (manual/scheduled)
- [x] T-S4-04 gate: YAML valid, first CI run green
- [x] T-S5-01 harness.py custom (N=5, mean/p95/outliers, JSON report)
- [x] T-S5-02 config.yaml (runs 5, tolerance 0.20)
- [x] T-S5-03 gate: harness run valid JSON, no pytest-benchmark
- [x] T-S6-01 playwright.config.ts (webServer uvicorn+vite, healthchecks)
- [x] T-S6-02 core-cycle.spec.ts (API seed → estadisticas → home)
- [x] T-S6-03 no AI Assistant E2E (scope guard)
- [x] T-S6-04 config flip (testing.coverage/e2e true, threshold 0)
