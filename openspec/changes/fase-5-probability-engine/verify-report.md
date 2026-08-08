```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:c887ea0cbd80381c8fd4d1eba0cf4c44caec219c7766dddc2352cf93e3e40700
verdict: fail
blockers: 3
critical_findings: 3
requirements: 6/18
scenarios: 11/20
test_command: backend/.venv/bin/pytest tests/probability/ -q
test_exit_code: 0
test_output_hash: sha256:a3638c3b18232bad9f4d04ebd00c9fb246cb391411c4a6f3c852c989c74a9d2f
build_command: backend/.venv/bin/ruff check .
build_exit_code: 1
build_output_hash: sha256:254ec8f2d93620ed4152b2dd2f0eb23b7916156adcba75993991aec195113929
```

# Verify Report: Fase 5 — Probability Engine

**Change**: fase-5-probability-engine
**Version**: spec 2026-08-08 · 18 requirements (PES-01..11 + PM-01..07) · 20 scenarios (13 PES + 7 PM)
**Mode**: Strict TDD (active, runner `backend/.venv/bin/pytest`)
**Store**: openspec · **HEAD**: 95b6742

## Executive Summary

**NO-GO.** The pure-math engine layer is correct and its 80 unit tests pass — but only with an **uncommitted
`backend/pyproject.toml` change** (pytest `--import-mode=importlib`). On the committed HEAD the suite fails at
collection (duplicate module basenames) and `ruff check .` fails with 21 errors (T-19 "final gates green" not met).
More critically, the **production generate path is broken**: the API and CLI construct `ProbabilityService` without
any reader adapters (T-13 adapters were never implemented), so every real `generate()` call crashes with
`AttributeError: 'NoneType' object has no attribute 'iter_draws'` — reproduced live for the service, the CLI, and
`POST /api/v1/probability/generate`. Even with mocks injected, the service persists **0 Monte Carlo rows** and
**0 conditional rows** (MC quantiles are never flattened into `prob_values`), and the empirical denominator
violates the PM-04 scenario. Git state is not clean. Verdict: **FAIL — fixes required before archive.**

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 19 |
| Tasks complete | 14 |
| Tasks incomplete | 5 (T-12 prod wiring, T-13 adapters, T-15 success-path, T-17 fixture e2e/read-only gate, T-19 ruff) |

## Build & Tests Execution

**Build (ruff)**: ❌ Failed — 21 errors (F401/I001/F841/E501) on `probability*`, service, API, tests.

```text
backend/.venv/bin/ruff check . → exit 1 (21 errors; 18 auto-fixable)
```

**Tests (probability suite)**: ✅ 80 passed (with worktree pytest config) — ❌ FAIL on committed HEAD
(collection error `import file mismatch` for `test_fingerprint.py`, `--import-mode=prepend` default)

```text
backend/.venv/bin/pytest tests/probability/ -q → 80 passed, 1 warning (0.41..9.6s)
Full suite (worktree config): 346 passed, 1 skipped
```

**Coverage**: ➖ Not available (no coverage tool configured).

## Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| PES-01 | writes confined to prob_* | (construction-only; no e2e read-only gate) | ⚠️ PARTIAL |
| PES-01 | MC persists aggregates/quantiles only | `test_monte_carlo_output_shape_and_no_raw_histories`; runtime: 0 MC rows persisted | ⚠️ PARTIAL |
| PES-02 | all non-prob rows unchanged | no covering test | ❌ UNTESTED |
| PES-03 | non-monotonic dates → draw_number axis | draw_number-only model; no explicit test | ⚠️ PARTIAL |
| PES-04 | locked snapshot survives bump | service version-bump tests | ✅ COMPLIANT |
| PES-05 | identical rerun matches | determinism 6/6 (seed, rerun equality, fingerprint) | ✅ COMPLIANT |
| PES-05 | MC param change → new deterministic run | `test_seed_changes_when_n_simulations_changes` | ✅ COMPLIANT |
| PES-06 | decoupled from F3/F4 internals | providers contract test; grep=0; no adapters | ⚠️ PARTIAL |
| PES-07 | replace retires, failure → failed | store lifecycle 10/10 | ✅ COMPLIANT |
| PES-08 | read never generates, 404 | service missing tests + API 404 | ✅ COMPLIANT |
| PES-09 | rollback drops only prob_* | migrations 12/12 (0007 up/down) | ✅ COMPLIANT |
| PES-10 | per-lottery isolation | lottery_id scope; no two-lottery test | ⚠️ PARTIAL |
| PES-11 | 0-draw handled gracefully | store/service fixture tests draw 0..0 | ✅ COMPLIANT |
| PM-01 | hypergeometric single-number odds | hand fixture (`C(9,5)` grid) | ✅ COMPLIANT |
| PM-02 | exact binomial | fixture `C(5,k)/32` | ✅ COMPLIANT |
| PM-03 | exact Poisson | fixture λ=2 | ✅ COMPLIANT |
| PM-04 | frequency-derived rate | engine fixture; service denominator wrong | ❌ UNTESTED (correct path) |
| PM-05 | seeded rerun identical | engine + determinism tests; 0 rows persisted | ⚠️ PARTIAL |
| PM-06 | same priors same posterior | engine rerun test; data not wired | ⚠️ PARTIAL |
| PM-07 | windowed univariate conditional | engine 8/20=0.4 fixture; 0 rows persisted | ⚠️ PARTIAL |

**Compliance summary**: 8/20 scenarios fully compliant (PES-04, PES-05×2, PES-07, PES-08, PES-09, PES-11, PM-01, PM-02, PM-03 — 10/20 flags hold); 6 of 18 requirements have delegated covering behavior (fail verdict valid).

## Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| PES-01/02 isolation | ✅ Implemented (construction) | writes to ProbSnapshot/ProbValue only |
| PES-04/05 determinism | ✅ Implemented | fingerprint + checksum + seed |
| PES-06 providers | ⚠️ Protocols only; adapters absent | service never wired in API/CLI |
| PM-01..07 engine funcs | ✅ Implemented | all match hand fixtures |
| PM-05/07 persistence | ❌ Broken | MC/conditional rows never written |
| PES-07 lifecycle | ✅ Implemented | store tests 10/10 |

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| D-A1 package parallel to F4 | ✅ | `probability/` + service + repos + API |
| D-A2 dict-dispatch registry | ✅ | `registry.py`, no Kahn |
| D-A3 consolidated snapshot_store | ✅ | single `prob_*` owner |
| D-A4 surrogate id PK + NULL grid rows | ✅ | models + migration |
| D-A5 empty → 0..0 header | ✅ | store/service tests; production blocked by adapter issue |
| D-A6 MC aggregates only | ⚠️ | aggregates computed but never persisted |
| D-A7 stdlib only (no scipy) | ✅ | math/Decimal/random |

## Issues Found

**CRITICAL**
1. T-13 adapter seam missing (PES-06/PES-02): API + CLI construct `ProbabilityService` with no readers →
   `generate()` crashes `AttributeError: 'NoneType' object has no attribute 'iter_draws'` (reproduced live: service,
   CLI, HTTP POST).
2. MC outputs never persisted (PM-05/PES-05): `_build_rows` looks for `mean/p50/p90/p99` top-level keys but the MC
   dict has `counts/probabilities/quantiles` → **0 MC rows** (reproduced: `monte_carlo persisted rows: 0`).
3. Conditional never persisted (PM-07): `params["window"]` never populated → **0 conditional rows** (reproduced).

**WARNING**
- Empirical denominator = sum(frequencies), not stat-snapshot draw count → PM-04 scenario (12/60=0.2) fails; plus
  service reads `stats_ref.snapshot_id` although `StatsSnapshotRef.id` — AttributeError with a real adapter.
- Bayes prior/likelihood hardcoded; "frozen input count data" never wired (PM-06).
- Suite green only via uncommitted `pyproject.toml` (design says unchanged); 21 ruff errors contradict
  tasks.md T-03/T-04/T-19 "ruff clean".
- T-17/T-15 tests missing: no fixture e2e (import→generate→read), no read-only FULL gate, no 201 generate test,
  no MC/conditional persistence assertions — the wiring bugs were invisible to the suite.
- `PROB_GENERATOR_VERSION` not imported by the service (hardcoded "1.0.0").
- Test file naming deviates from tasks.md (`tests/probability/test_api.py` vs `tests/api/test_probability_api.py`).

**SUGGESTION**
- MC two-pass (placeholder seed) — wasteful but deterministic.
- Fix ruff F401s (18 auto-fixable) and E501s.
- Add explicit multi-lottery isolation test and non-monotonic date test.
- Persist `apply-progress` with TDD Cycle Evidence table in the change dir (absent — strict TDD evidence only
  exists as inline status notes in tasks.md).

## Verdict

**FAIL — NO-GO.** Fixes required before archive:

1. **Implement the T-13 adapter seam** in `probability_service.py` (wraps `statistics_service.read_*`,
   `feature_engine_service.read_*`) and inject it in API + CLI generate paths; add a service integration test that
   exercises the real adapters.
2. **Fix MC flattening** so `prob_values` stores per-subject MC probabilities + `p50/p90/p99` quantiles (PM-05);
   assert MC rows exist and match rerun checksum.
3. **Wire the conditional window** from real provider/draw data (PM-07) and persist its rows.
4. **Fix the empirical denominator** to stat-snapshot draw count; align `StatsSnapshotRef.id` usage.
5. **Wire Bayes priors/likelihood** from declared frozen params (PM-06) and add rerun-checksum assertions.
6. **Commit the pytest import-mode change** (or rename colliding test files); restore `ruff check` clean.
7. **Add the promised e2e flow**: fixture import → generate → GET reads + read-only gate test.

(A serpentine double-check: the 80 unit tests pass because mocks inject readers into the service; the real wiring
path is never exercised by the suite — that is the core verification gap this report exposes.)