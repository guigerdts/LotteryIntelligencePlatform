# Exploration: Fase 17 — Testing (next SDD phase)

Scope: prepare a change proposal for Fase 17 per `IMPLEMENTATION_ROADMAP.md` (lines 354–368). Downstream dependencies noted only: Fase 18 (Documentación) and Fase 19 (Release Candidate) depend on a verifiable testing baseline.

## Current State

Fase 16 (Performance) is complete (PRs #39–#48, origin/main = `bee4941`). The repo has no CI, no coverage tooling, and no browser E2E tooling. Testing today is a large pytest suite plus a young vitest suite.

### Backend test inventory (1413 tests collected, `pytest --collect-only`)

| Area | Test file(s) | Count |
|---|---|---|
| Backtesting | `tests/bt/` | 178 |
| Generator | `tests/gen/` | 145 |
| Meta | `tests/meta/` | 138 |
| Optimization | `tests/opt/` (+ `test_opt_pr1.py`) | 129 + 9 |
| Deep learning | `tests/dl/` (+ `test_dl_pr1.py`) | 127 + 9 |
| Graph | `tests/graph/` | 116 |
| Probability | `tests/probability/` | 82 |
| Feature engineering | `tests/feature_engineering/` (+ `test_feature_engine_e2e.py`) | 48 + 4 |
| API | `tests/api/` | 36 |
| AI assistant | `tests/ai/` | 29 |
| ML | `tests/ml/` (+ `test_ml_pr1..pr5`) | 7 + 39 |
| Statistics | `tests/statistics/` (+ `test_statistics_api.py`) | 20 + 13 |
| Experiments | `test_exp_*` (store/service/api/errors/comparison/export) | 86 |
| Import | `test_import_*` (core/service/api) | 49 |
| Services | `test_services.py` | 31 — **BROKEN** |
| Integrity | `test_integrity.py` | 20 — **BROKEN** |
| Migrations | `test_migrations.py` | 16 |
| CRUD/dataset/registry | `test_crud_*`, `test_dataset_generate.py`, `test_registry_isolation.py` | 39 |
| Response cache (F16) | `test_response_cache.py` | 7 |
| API errors | `test_api_errors.py`, `test_exp_api_errors.py` | 20 |
| Cold start (F16 S6) | `test_cold_start.py` | 3 |
| Isolation guard (F16 S7) | `test_isolation_guard.py` | 2 |
| Determinism (F6) | `test_determinism.py` | 2 |
| Dialect compat | `test_dialect_compat.py` | 3 |
| Smoke/config | `test_smoke.py`, `test_config.py` | 5 |

Every engine has dedicated tests. 63 of them are currently BROKEN by a fixture regression.

### Measured evidence

- **Backend coverage: NOT MEASURABLE.** Neither `pytest-cov` nor `coverage.py` is installed in `backend/.venv`; `pyproject.toml` has no `[tool.coverage]` section; `openspec/config.yaml` has `coverage: false`. Per exploration constraints, nothing was installed. Coverage must be estimated from inventory: engines are well tested, but the largest modules — `services/` (5,140 lines), `models/` (2,154), `cli.py` (1,281), `repositories/` (1,247), `schemas/` (968) — are only exercised indirectly, and the dedicated `test_services.py` is broken. Realistic estimate: **~55–75% backend**, unverifiable today.
- **Backend suite runtime: > 15 min full** (killed at 920 s; no OOM on this 7.4 GB box, it is just slow — DL/ML/opt training tests). The S7 conftest docstring itself warns the suite peaks ~1 GB and recommends per-directory runs on 2.4 GB boxes. Bounded subset measured: `tests/api` + `tests/statistics` + `tests/probability` + `test_services.py` + `test_smoke.py` + `test_api_errors.py` + `test_cold_start.py` + `test_isolation_guard.py` + `test_config.py` → **161 passed, 31 errors in 165 s**.
- **63 backend tests ERROR with `ScopeMismatch`** (regression introduced by F16 S7, PR #48): `tests/conftest.py` now defines `migrated_db` as **session-scoped** (line 67) and the autouse `_reset_outer_transaction(connection)` chain requires it; three legacy modules still define their own **function-scoped** `migrated_db(tmp_path)` which shadows it → setup error for every test in the module: `test_services.py` (31), `test_integrity.py` (20), `test_import_service.py` (12). The F16 "all tests pass" claim does not hold for these modules.
- **Frontend: 129 tests in 20 files** (`vitest`, jsdom, `@testing-library/react`, `msw`, `./src/test/setup.ts`). Measured run: **3 failed / 126 passed** (History pagination 5 s timeout; Networks `findByTestId("network-graph")`; one more render failure). **No coverage tooling**: `@vitest/coverage-v8` absent, no `coverage` block in `vite.config.ts`. Frontend coverage is unmeasurable and likely **< 70%** (pages are smoke-tested; `DataTable`, `EmptyState`, `ErrorState`, `Header`, `NavGroup`, `NavItem`, `Skeleton`, `hooks/`, most chart variants, `DashboardLayout` have no direct tests).
- **Performance/regression**: `test_cold_start.py` (3) asserts heavy deps are not loaded at import; `test_response_cache.py` (7) covers the F16 cache; `tests/bt/test_benchmark.py` tests the *correctness* of benchmark strategies, NOT a performance harness. No `pytest-benchmark`, no timing thresholds, no sustained perf regression suite.
- **E2E**: only backend CLI/API-level "e2e"-named tests exist (`test_bt_e2e.py`, `test_graph_e2e.py`, `test_opt_e2e.py`, `test_ml_determinism_e2e.py`, `test_probability/e2e.py`, `test_feature_engine_e2e.py`). No Playwright/Cypress anywhere.
- **No CI**: no `.github/workflows`, no Makefile/tox/nox. Nothing gates coverage or enforces the roadmap targets.

### Fase 17 test-type matrix (roadmap requires: unit, integration, E2E, performance, regression)

| Type | Status | Evidence |
|---|---|---|
| Unit | Covered | Engine-level tests across all engines |
| Integration | Partially covered, broken | 63 `ScopeMismatch` errors; migration/repo/service tests exist |
| End-to-End | Missing (as browser E2E) | Only backend CLI/API acceptance-style tests |
| Performance | Partial | Cold-start + cache tests; no benchmark harness with thresholds |
| Regression | De facto only | Determinism/parity/isolation guards; no named regression suite or gate |

## Affected Areas

- `backend/tests/conftest.py` — S7 session-scoped `migrated_db`; source of the `ScopeMismatch` regression; central to any coverage run.
- `backend/tests/test_services.py`, `tests/test_integrity.py`, `tests/test_import_service.py` — legacy function-scoped `migrated_db` shadow; 63 broken tests to repair.
- `backend/pyproject.toml` — needs `pytest-cov`/`[tool.coverage]` (and possibly `pytest-benchmark`) to make the ≥80% backend target measurable.
- `backend/.venv` — coverage dependencies absent; requires a `uv sync`-level change (a decision for the proposal phase).
- `frontend/package.json` + `frontend/vite.config.ts` — needs `@vitest/coverage-v8` and a `coverage` block to make the ≥70% frontend target measurable.
- `openspec/config.yaml` — `testing.coverage: false`, `testing.e2e: false`, `verify.coverage_threshold: 0` must be updated after implementation.
- `openspec/specs/` — no testing domain spec exists; Fase 17 needs a new delta spec domain (e.g. `testing/`).
- `frontend/src/pages/History.test.tsx`, `Networks.test.tsx` (+1) — 3 currently failing frontend tests.

## Approaches

1. **Fix-and-measure (repair first, then instrument)** — Task 0 repairs the 63 `ScopeMismatch` errors and 3 frontend failures; then add `pytest-cov` + `@vitest/coverage-v8`, measure, and fill gaps.
   - Pros: green baseline before any measurement; unblocks `test_services.py` coverage contribution; small, well-understood fixes.
   - Cons: measurement is delayed by the repair; some may argue broken tests are outside Fase 17 scope (they are a pre-existing regression, so they belong to "regression" work).
   - Effort: Low (repair) + Medium (instrument) — recommended as the opening slice.
2. **Instrument-first (measure before fixing)** — add coverage tooling now, record the true baseline, then repair and fill gaps against a published number.
   - Pros: data-driven; the exploration's estimate (~55–75% backend) gets replaced by a real number before any test-writing effort.
   - Cons: the 63 broken tests will distort the baseline and coverage report until fixed.
   - Effort: Medium.
3. **Type-by-type rollout** — treat the five roadmap types as sequential slices (unit/integration → regression → performance → E2E) with per-type DoD, saving browser E2E for last.
   - Pros: matches the roadmap structure; each slice is reviewable within the 400-line guard; E2E stack decision lands last when the rest is stable.
   - Cons: slowest path to the coverage gates; E2E remains undecided longest.
   - Effort: High (total), but each slice Medium.

## Recommendation

**Approach 1 (fix-and-measure) with E2E deferred as a user-decided slice at the end.** Concretely: (1) repair the 63 `ScopeMismatch` errors by aligning the three legacy modules with the S7 session-scoped fixture (or making conftest's `migrated_db` per-module-compatible), plus the 3 frontend failures; (2) add `pytest-cov` with `--cov=backend.app` and `@vitest/coverage-v8` and publish the real baseline; (3) fill the largest gaps — `services/` layer (5,140 lines) and frontend components (pages are smoke-tested only); (4) add a CI or pre-commit gate enforcing ≥80% backend / ≥70% frontend (or report-only if the user prefers); (5) add a performance slice only if the user wants thresholds (pytest-benchmark is a new dependency); (6) browser E2E last, pending the user's stack choice. Everything before the E2E slice stays inside a single-reviewable change; E2E can be a follow-up change if the user defers it.

## Risks

- **Coverage targets may be unreachable as stated**: frontend ≥70% is questionable with a thin dashboard (129 tests, 3 failing, no coverage config, many components untested); backend ≥80% requires closing the services/model/repo/schema gap that is today only indirectly tested. The proposal must decide whether targets are hard gates or initial goals.
- **Suite runtime vs CI**: backend full suite > 15 min and ~1 GB peak; a CI coverage gate on every push needs per-directory sharding or a reduced gate subset.
- **E2E cost**: browser E2E requires a running app, Playwright/Cypress infra, and per-page selectors — the largest single slice; must be user-approved.
- **Coverage-dependency additions** (pytest-cov, @vitest/coverage-v8, possibly pytest-benchmark) touch `pyproject.toml`/`package.json` — a dependency change the proposal must record.
- **63 broken tests today** contradict the "all tests pass" DoD claim for F16; if left unfixed, every coverage number stays distorted.

## Open Decisions (user must decide)

1. **Coverage gate policy**: hard CI gate that fails below 80/70, or report-only gates in Fase 17 with enforcement later?
2. **Frontend scope**: is frontend ≥70% genuinely in scope for this repo (thin dashboard), or should Fase 17 focus backend ≥80% and treat frontend coverage as best-effort?
3. **E2E stack**: Playwright (recommended) vs Cypress vs "backend acceptance e2e is sufficient" — and whether E2E ships in this change or a follow-up.
4. **Performance harness**: pytest-benchmark with thresholds vs timing assertions vs manual scripts — and whether perf gates run in CI.
5. **CI provider**: none exists; GitHub Actions vs pre-commit-only gates — a prerequisite for any enforced coverage gate.

## Ready for Proposal

Yes — with the caveats above. The orchestrator should tell the user: Fase 17 is confirmed as the next phase; 63 backend tests and 3 frontend tests are currently broken (F16 S7 fixture regression); coverage is unmeasurable today on both stacks; and the five open decisions above must be resolved before proposal/spec. Artifact persisted at `openspec/changes/explorar-siguiente-fase/exploration.md`.