# Exploration — fase-19-release-candidate

**Date**: 2026-08-21
**Roadmap source**: `IMPLEMENTATION_ROADMAP.md` lines 384–394
**Phase chain**: ... → F16 Performance → F17 Testing → F18 Documentation (archived 951c6bd) → **F19 Release Candidate** — final phase of the roadmap.

## Roadmap scope (verbatim)

- Auditoría de código.
- Corrección de errores críticos.
- Validación funcional.
- Validación de rendimiento.
- Congelamiento de funcionalidades.
- Preparación para versión 1.0.

## Audit baseline (measured 2026-08-21, HEAD 951c6bd)

### Static analysis
- `backend/.venv/bin/ruff check .`: **All checks passed** (exit 0). F18 S0 cleared the 26 pre-existing errors; zero regressions since.
- TODO/FIXME/XXX/HACK markers in `backend/app/` + `frontend/src/`: **0**.

### Known debt inventory (verified against repo)
| Item | Verified state |
|---|---|
| Optuna tests/opt | `import optuna` → ModuleNotFoundError in backend/.venv. pyproject.toml lines 41–48 declare BOTH `deap==1.4.1` AND optuna as the only permitted runtime deps for opt/ engines. Full suite: **5 failed / 1429 passed / 1 skipped** (329 s) — all 5 failures are tests/opt ModuleNotFoundError family. Root cause: deps declared but never installed into the venv. |
| Perf baselines | Harness EXISTS: `backend/tests/performance/harness.py` + `config.yaml` (F17 TEST-006/ADR-6). 3 ops: cold_start, cached_statistics_get, parallel_bt_train. First calibration run 2026-08-20: cold_start measured ~13–17 s vs 5.6 s design estimate (**flagged FAIL — real signal**); stats GET ~0.03–0.06 s and parallel bt ~0.37–0.6 s OK. Runs on demand via `.github/workflows/performance.yml`; NOT a PR gate. |
| uv.lock stale | `backend/uv.lock` dated 2026-08-09 vs `pyproject.toml` 2026-08-19 — lock predates the deap/optuna declaration edits. |
| LICENSE/CHANGELOG | Confirmed absent at repo root. |

### Functional validation
- Backend: **5 failed / 1429 passed / 1 skipped** (only tests/opt import failures).
- Frontend vitest full suite: **FLAKY**. Run A: 1 failed / 136 passed. Run B (verbose): 3 failed (`App.test.tsx` router navigation, `Experiments.test.tsx` skeleton, `History.test.tsx` pagination). Same 3 files in isolation: **17/17 PASSED**. Diagnosis: timing/resource contention under full-suite load, not product regressions. This is a release-blocker-class finding for "Validación funcional" credibility.
- E2E: `frontend/e2e/core-cycle.spec.ts` exists (Playwright ^1.62.1); F17 closed with E2E 1/1 green.
- Coverage at F17 close: backend 91.88%, frontend 95.22% (CI report-only).

### Performance validation readiness
- Harness is runnable and produces a JSON report; exit contract: 0 when measured+written (regressions are data, not gate failures).
- Open item: cold_start baseline mismatch (13–17 s actual vs 5.6 s estimate) needs either baseline recalibration or investigation before v1.0 performance evidence.

### Feature-freeze readiness
- DL engine intentionally has NO router mounted (documented in MANUAL_TECNICO §11 and ENGINE_SPECIFICATIONS §10) — by-design scope boundary, not half-finished work.
- CI: workflows dir present incl. performance.yml; coverage checks are report-only (F17 decision, 3-consecutive-runs rule).
- Git tags exist per phase through fase-5 pattern (5 tags total); no v-prefixed semver tags yet.
- Versions: backend pyproject `0.1.0`, frontend package.json `0.1.0`.

### Version 1.0 preparation gaps
1. No LICENSE file (owner decision pending since F18 — documented absence).
2. No CHANGELOG.md.
3. Version strings still 0.1.0 in both manifests.
4. No git tag convention for releases (phase tags only).
5. uv.lock out of sync with pyproject.toml.
6. Frontend flaky tests (see above).
7. Optuna/deap not installed in venv despite being declared runtime deps.

## Key questions F19 must answer

1. Does "Auditoría de código" mean introducing new tooling (mypy/bandit) or auditing with existing gates? Existing gates are ruff+pytest+vitest+playwright; no type checker configured.
2. Are the 5 optuna test failures fixed by installing deps (venv-level, mechanical) or by marking them skip-until-installed? Installing changes the venv; skipping changes the suite contract.
3. Is cold_start FAIL a real regression to investigate or an estimate to recalibrate?
4. What does "Congelamiento de funcionalidades" concretely require — a tag, a branch policy, a docs statement?
5. v1.0 versioning: bump both manifests to 1.0.0 + first semver git tag?
6. LICENSE choice remains an owner decision (blocked since F18).

## Risks

- Flaky frontend tests may block a clean "all green" release validation run.
- Installing optuna/deap pulls sizable dependency trees into the venv (reproducibility implications; uv.lock must be regenerated consistently).
- Perf harness cold_start numbers are box-noise sensitive (13–17 s swing observed).

## Next recommended phase

sdd-propose for `fase-19-release-candidate`.
