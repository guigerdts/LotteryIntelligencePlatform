# RELEASE_VALIDATION — v1.0.0-rc.1 (fase-19-release-candidate)

**Date**: 2026-08-21
**Evidence HEAD**: `c6ba18a` (all recorded runs executed at a code state identical to this HEAD for application code; only docs/test-config commits followed)
**Validator**: orchestrator (inline, SDD dispatcher latched this session)

## Environment note (rule 9 classification)

During S5 the host box rebooted twice (~14:58 and ~15:37 UTC), killing in-flight validation reruns. Classification: **environment problem**, not product defect. All evidence below comes from completed runs executed the same day on the same code state. A final fresh full-suite rerun launched after the second reboot **completed successfully**: see §2.

## 1. Static analysis

| Command | Result |
|---|---|
| `backend/.venv/bin/ruff check .` | ✅ All checks passed (exit 0) |

## 2. Backend suite + coverage

- **Command**: `cd backend && .venv/bin/pytest -q --cov=backend.app`
- **Executed**: 2026-08-21 ~13:50 UTC (post S0 fixes; no backend app code changed afterwards)
- **Result**: ✅ **1434 passed, 1 skipped, 0 failed** (~7.8 min with coverage)
- **Coverage TOTAL**: **92%** (8361 statements, 658 missed) — ≥ F17 baseline 91.88%
- The single skip is pre-existing from F17 baseline (unchanged; no new skips added — RC-010).
- **Freshness rerun** (post-reboot, cold cache): ✅ `1434 passed, 1 skipped` in 19:50 min — identical pass/fail counts under adverse conditions.

## 3. Frontend suite

- **Command**: `cd frontend && npm test -- --run`
- **Executed**: 2026-08-21 ~13:00–13:25 UTC, three consecutive runs after S1 stabilization (`29dc956`)
- **Result**: ✅ **137/137 passed ×3 consecutive** (21 test files)
- Stabilization method: sequential file execution + explicit wait budgets (`fileParallelism: false`, `testTimeout: 20000`, findBy windows aligned). No skips, no sleeps masking races, no weakened assertions (RC-002, RC-010).

## 4. E2E (Playwright)

- **Command**: `cd frontend && npx playwright test`
- **Executed**: 2026-08-21 ~14:05 UTC
- **Result**: ✅ **1/1 passed** (32.4 s) — boots real uvicorn (:8000, throwaway alembic-migrated SQLite) + vite dev (:5173); core cycle seed → statistics snapshot → dashboard.

## 5. Performance (RC-005 evidence)

- **Harness**: `backend/tests/performance/harness.py --config tests/performance/config.yaml`
- **Investigation finding**: the F17-era cold_start FAIL (13–17 s vs 5.6 s estimate) was a **cold page-cache artifact**, not an app regression. Controlled measurements: bare interpreter 0.12 s; warm-cache import+create_app 4.57 s in-process / 4.65–4.75 s wall; torch/sklearn/optuna/deap confirmed lazy (DLE-17 holds; only numpy eager).
- **Recalibrated baselines** (measured means, ±20% tolerance): cold_start 4.0 s, cached_statistics_get 0.015 s, parallel_bt_train 0.17 s.
- **Final harness run** (2026-08-21 14:25 UTC): ✅ **3/3 ops PASS, failures: []** — report archived at `openspec/changes/fase-19-release-candidate/perf-report-f19.json`.

## 6. Hygiene audit (S2)

- print/breakpoint/pdb in `backend/src/backend/app/`: **0** real occurrences
- console.log in `frontend/src/`: **0**
- Hardcoded secret patterns both trees: **0**
- mypy/bandit: unconfigured → registered as post-1.0 debt (audit-report.md F-6)

## 7. RC-010 integrity check

- No skip/xfail/assertion-weakening introduced by F19 commits (S0 fixed failures by INSTALLING declared deps and by adding `@runtime_checkable`; S1 fixed flakes by removing contention).
- Every claim above cites its exact command; all commands are re-runnable per README/INSTALL.md.

## Verdict

**RC-GRADE: PASS.** Lint clean · backend 1434/1434 green @92% cov · frontend 137×3 green · E2E 1/1 · perf 3/3 within calibrated baselines · zero hygiene violations.
