# Coverage Baseline — Fase 17 (TEST-002, Slice S2)

**Date**: 2026-08-19
**Branch**: `fase-17-testing/s2-coverage` (from origin/main @ 5998838)
**Change**: fase-17-testing · **Spec**: TEST-002 (Coverage Instrumentation)
**Gate**: Report-only baseline (ADR-3 / D1) — recorded, NOT a gate failure. No `fail_under` set anywhere.

## Measured Numbers

| Metric | Value |
|--------|-------|
| **Backend coverage (statements)** | **90.05%** (7506 / 8335 statements, 829 missing) |
| **Frontend coverage (statements/lines)** | **94.59%** (2992 / 3163 statements) |
| Frontend branches | 88.49% (700 / 791) |
| Frontend functions | 85.65% (203 / 237) |

Targets for the later hard gate (TEST-003): backend ≥80% ✓ (already above), frontend ≥70% ✓ (already above). Hard gate activates only after 3 consecutive qualifying CI runs (`coverage-history.json`).

## How Measured

### Backend

- Tooling: `pytest-cov==7.1.0` + `coverage==7.15.4` installed into `backend/.venv` via `uv pip install` (project mechanism; `uv sync` cannot resolve `torch==2.13.0+cpu` without the PyTorch index — uv.lock is stale, missing torch/deap/optuna).
- Command per group (suite peaks ~1 GB — memory limit, not a defect; run strictly per-directory, `pkill -9 -f pytest` between groups):

```
COVERAGE_FILE=.coverage.<group> timeout 2200 backend/.venv/bin/python -m pytest <files> -q -p no:warnings \
  --cov=backend.app --cov-report=json --cov-report=term
```

- Groups (mirrors S1 full-suite split; combined via `coverage combine`):

| Group | Tests | Result | Group-local statements covered |
|-------|-------|--------|-------------------------------|
| tests/ai | 29 | 29 passed | 4821/8335 (42%) |
| tests/api | 36 | 36 passed | 4103/8335 (51%) |
| tests/bt | 178 | 178 passed | 4364/8335 (48%) |
| tests/dl | 127 | 127 passed | 4487/8335 (46%) |
| tests/feature_engineering | 48 | 48 passed | 4593/8335 (45%) |
| tests/gen | 145 | 145 passed | 4376/8335 (47%) |
| tests/graph | 116 | 116 passed | 4636/8335 (44%) |
| tests/meta | 138 | 138 passed | 4480/8335 (46%) |
| tests/ml | 7 | 7 passed | 4598/8335 (45%) |
| tests/opt | 129 | 124 passed, **5 pre-existing failures** (out of scope, see below) | 4394/8335 (47%) |
| tests/probability | 82 | 82 passed | 4331/8335 (48%) |
| tests/statistics | 20 | 20 passed | 4707/8335 (44%) |
| root-pr (ml_pr1-5, opt_pr1, dl_pr1) | 65 | 65 passed | 4337/8335 (48%) |
| root-p0 (isolation_guard, registry_isolation) | 8 | 8 passed | 4324/8335 (48%) |
| root-misc1 (api_errors, cold_start, config, crud_*) | 45 | 45 passed | 4691/8335 (44%) |
| root-exp (exp_*) | 86 | 86 passed | 4668/8335 (44%) |
| root-misc2 (dataset, determinism, dialect, imports, integrity, migrations, services, smoke, statistics_api) | 154 | 153 passed + 1 intentional skip | 3661/8335 (56%) |

- Totals: **1407 passed + 1 skip + 5 pre-existing opt failures** — identical to the S1 full-suite result; suite state unchanged by S2.
- Combine: `coverage combine` (17 `.coverage.<group>` files) → `coverage report --data-file=.coverage` → **90.05%**; JSON summary in `coverage.json` (gitignored).
- Per-group percentages look low (42–56%) because each group alone exercises only part of `backend.app`; the combined full-suite number is the official baseline.

### Frontend

- Tooling: `@vitest/coverage-v8@3.2.7` (matches vitest 3.2.x) + `coverage` block in `frontend/vite.config.ts` (provider v8, reporters text/json-summary/html, include `src/**`).
- Command: `npx vitest run --coverage` → **129 passed (20 files)**.
- Coverage summary: `frontend/coverage/coverage-summary.json` (gitignored).

## Known Exclusions / Findings

- **5 pre-existing failures in `tests/opt`** (reported separately per TEST-001 scenario 3, NOT part of S2, NOT folded into the baseline): 4× `test_bayesian.py` `ModuleNotFoundError: No module named 'optuna'` + 1× `test_engine.py` non-runtime-checkable protocol TypeError. Present on clean origin/main; S2 does not touch them.
- **pytest-cov ≥7.0 renamed the `json-summary` report alias to `json`** (same `coverage.json` summary output). Used `--cov-report=json`; the S4 CI script must use `json` or the coverage CLI equivalent.
- **App.test.tsx lazy-chunk tests** (Suspense fallback + Home render) hit vitest's default 5 s test timeout under coverage overhead; raised per-test timeout to 15 s (same hardening S1 applied to the /ia test). Test-only change.

## Rollback

Revert T-S2-01/02/03 commits: remove `pytest-cov` + `[tool.coverage]` (pyproject.toml), remove `@vitest/coverage-v8` + vite coverage block (package.json, vite.config.ts), delete `coverage-history.json`, revert the App.test.tsx timeout bump. No production code touched.