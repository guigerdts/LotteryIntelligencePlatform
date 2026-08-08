```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:e681895c1cd358567cadefbcd6fc9c712d6d017ad1772ac74fce7e9ad35eb3f5
verdict: fail
blockers: 1
critical_findings: 1
requirements: 14/18
scenarios: 16/20
test_command: backend/.venv/bin/pytest tests/probability/ -v
test_exit_code: 0
test_output_hash: sha256:26bc39c9a3c3a6c07b4e8f82267800727f71bcd867aad1ef77a695efa5408b10
build_command: backend/.venv/bin/ruff check src/backend/app/probability/ src/backend/app/services/probability_service.py src/backend/app/api/v1/probability.py src/backend/app/schemas/probability.py
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

# Re-Verify Report: Fase 5 - Probability Engine

**HEAD**: 5f0d86a · **Previous**: 95b6742 (NO-GO: 3 CRITICAL + 4 HIGH)

## Executive Summary

All 9 checklist gates PASS, but the authoritative verdict is **fail** (validated by
`gentle-ai sdd-verify-validate`, which denied a `pass` on incomplete evidence).

What was previously broken is now fixed and verified:
- C1: `_DrawReaderAdapter`, `_StatsReaderAdapter`, `_FeatureReaderAdapter` exist, are auto-created,
  and the API (`ProbabilityService(db)`) and CLI (`ProbabilityService(session)`) no longer crash.
- C2: `_build_rows` persists per-subject `probabilities` (subjects `prob_N`) plus `p50/p90/p99`
  quantiles from the real `{counts, probabilities, quantiles}` MC structure; no `mean` anywhere.
- C3: the conditional window is populated from actual draws (`draws[-20:]`), never an empty dict.
- H1: empirical denominator is `len(draws)`, not `sum(stat_frequencies.values())`.
- H2: Bayes uses declared params with fallback defaults; H3: adapter resolves `snap.id`;
  H4: ruff is clean (the previous 21 errors are gone).
- The pytest `--import-mode=importlib` setting is committed, so the suite is green on HEAD.

Runtime evidence: `tests/probability/` = 80 passed (exit 0); full suite = 346 passed, 1 skipped;
ruff on all four target paths = exit 0; tree clean at `5f0d86a`; both isolation greps and the
out-of-scope grep return empty.

What still blocks archive: (1) the conditional divisor mismatch (both sources of truth for
window size disagree - see CRITICAL below), a defect the current suite cannot catch;
(2) the PES-02 byte-identical read-only gate and PES-01-s1 still lack runtime covering tests
(UNTESTED); (3) PES-03 and PES-10 remain PARTIAL.

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 19 |
| Tasks complete | 19 |
| Tasks incomplete | 0 |

## Gate Results

| 1. Tests | PASS |

`backend/.venv/bin/pytest tests/probability/ -v` - 80 passed, 1 warning, exit 0 (6.41s).
Full suite `pytest -q` - 346 passed, 1 skipped, exit 0 (271s).

| 2. Ruff clean | PASS |

`ruff check src/backend/app/probability/ src/backend/app/services/probability_service.py
src/backend/app/api/v1/probability.py src/backend/app/schemas/probability.py` - "All checks passed!", exit 0.

| 3. C1 (adapters) | PASS |

`_DrawReaderAdapter` (line 62), `_StatsReaderAdapter` (line 90), `_FeatureReaderAdapter` (line 128)
in `services/probability_service.py`; each auto-created when its reader arg is None (lines 161-169).
API constructs `ProbabilityService(db)` (api/v1/probability.py lines 53, 94); CLI constructs
`ProbabilityService(session)` (cli.py lines 290, 311). Providers contract test
`test_package_modules_stay_decoupled_from_concrete_seams` passes.

| 4. C2 (MC persistence) | PASS |

`_build_rows` (lines 467-491) persists `probabilities` as `prob_<subject>` rows and `quantiles`
as p50/p90/p99 rows; engine returns exactly `{counts, probabilities, quantiles}` (engine.py line 121).
`grep mean` on `probability/` + service -> no match. Test `test_monte_carlo_output_shape_and_no_raw_histories`
passes (`set(result["probabilities"])` and `set(result["quantiles"]) == {"p50","p90","p99"}`).

| 5. C3 (conditional) | PASS |

`_compute_execution` (lines 287-292) builds `conditional_window` from `draws[-20:]` real draws and
passes it to `conditional(...)`; rows are persisted. Not an empty dict anymore. (Divisor concern:
see CRITICAL below.)

| 6. H1 (empirical) | PASS |

Service uses `total = len(draws)` (line 320). Engine fixture `test_empirical_spec_scenario_twelve_out_of_sixty`
(12/60 = 0.2) passes.

| 7. Isolation | PASS |

`grep -r "from backend.app.statistics" backend/src/backend/app/probability/` -> empty (exit 1).
`grep -r "from backend.app.feature_engineering" .../probability/` -> empty (exit 1).
Concrete imports appear only inside the composition-root adapters (PES-06/FES-06 parity).

| 8. Git state | PASS |

HEAD = `5f0d86a` ("fix(probability): resolve 3 CRITICAL + 4 HIGH"); `git status --short` empty.

| 9. No out-of-scope | PASS |

`grep -ri "prediction|sklearn|tensorflow|bet|wager" .../probability/` -> empty (exit 1).

## Spec Compliance Matrix (20 scenarios)

| Requirement | Scenario | Status | Evidence |
|-------------|----------|--------|----------|
| PES-01 | writes confined to prob_* | PARTIAL | construction-level only; no runtime gate |
| PES-01 | MC never persists raw runs | COMPLIANT | shape test + aggregates-only flattening |
| PES-02 | all non-prob rows unchanged | UNTESTED | no byte-identical run gate |
| PES-03 | non-monotonic dates | PARTIAL | draw_number model only; no explicit test |
| PES-04 | locked snapshot survives bump | COMPLIANT | full-vs-incremental version tests |
| PES-05 | identical rerun matches | COMPLIANT | fingerprint + seed determinism tests |
| PES-05 | MC param change new run | COMPLIANT | test_seed_changes_when_n_simulations_changes |
| PES-06 | decoupled from F3/F4 | COMPLIANT | providers contract + empty greps |
| PES-07 | replace retires, failure-failed | COMPLIANT | store lifecycle tests |
| PES-08 | read never generates, 404 | COMPLIANT | test_read_never_precomputes + API 404 |
| PES-09 | migration up/down prob-only | COMPLIANT | test_upgrade_0007... / downgrades |
| PES-10 | per-lottery isolation | PARTIAL | lottery_id scoping; no two-lottery test |
| PES-11 | 0-draw handled gracefully | COMPLIANT | empty-store tests + 0..0 header tests |
| PM-01 | hypergeometric hand odds | COMPLIANT | engine fixture |
| PM-02 | exact binomial | COMPLIANT | engine fixture C(5,k)/32 |
| PM-03 | exact Poisson | COMPLIANT | engine fixture lambda=2 |
| PM-04 | frequency-derived 12/60 | COMPLIANT | engine fixture 12/60=0.2 + H1 service |
| PM-05 | seeded rerun identical | COMPLIANT | engine deterministic tests |
| PM-06 | same priors same posterior | COMPLIANT | bayes deterministic tests |
| PM-07 | windowed univariate 8/20 | COMPLIANT (engine) | engine fixtures; service wiring deviates |

**Compliance summary**: 16/20 scenarios compliant, 1 UNTESTED (PES-02), 3 PARTIAL (PES-01 s1,
PES-03, PES-10). Requirements fully covered: 14/18.

## Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| PES-01/02 isolation | Implemented | writes only ProbSnapshot/ProbValue via require read-only |
| PES-04/05 determinism | Implemented | canonical fingerprint + checksum + seed policy |
| PES-06 providers | Implemented | protocols + adapters wrap services only |
| PES-07 lifecycle | Implemented | one active per (lottery_id, model_set) |
| PES-08 manual-only | Implemented | CLI/API generate; read = 404, no precompute |
| PM-01..07 | Implemented | all hand fixtures match; no float outputs |

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| D-A1 package parallel to F4 | yes | probability/ + service + models + API + CLI |
| D-A2 dict-dispatch registry | yes | registry.py, no Kahn |
| D-A3 consolidated store | yes | snapshot_store owns prob_* |
| D-A4 surrogate id PK / NULL grids | yes | ORM + 0007 migration |
| D-A5 empty -> 0..0 header | yes | tests + wiring |
| D-A6 MC aggregates only | yes | engine + persistence match |
| D-A7 stdlib only | yes | math/Decimal/random |

## Issues Found

**CRITICAL (1)**
1. Conditional divisor / window mismatch (PM-07): `_compute_execution` counts the window over
   `draws[-20:]` (lines 288-292) but divides by `params["window_size"] or 10` (line 345, registry
   default `window_size: None`). For a small-pool lottery a single number can appear in more than
   10 of the last 20 draws, persisting a value > 1.0, and the 8-in-20 fixture would
   persist 8/10 = 0.8 instead of 0.4. The two sources of "window size" disagree. There is no
   service-level test asserting a persisted conditional value, so the suite cannot catch this.

**WARNING**
- PES-02 byte-identical read-only runtime gate is UNTESTED (the T-17 promise).
- PES-01-s1, PES-03, PES-10 lack runtime coverage (construction-level evidence only).

**SUGGESTION**
- Make window slicing and divisor a single constant: `draws[-window_size:]` with default 20, and
  add a service test with a fixture asserting persisted conditional rows.
- Add a PES-02 gate (snapshot Core/stat_*/feature_* rows before/after and byte-compare).
- Test file names deviate from tasks.md (`test_api.py`, `test_e2e.py` under tests/probability/).

## Verdict

**NO-GO (verdict: fail)** - blockers 1, critical findings 1, requirements 14/18, scenarios 16/20.

All 9 checklist gates and 80/80 + 346/346 tests are green and the previous 3 CRITICAL + 4 HIGH fixes
are verified in code and by runtime tests, but `gentle-ai sdd-verify-validate` correctly rejects a
`pass` on incomplete evidence and one genuine CRITICAL (conditional divisor mismatch, no covering
test) remains. The change is not archive-ready; a small targeted fix (consistent window divisor +
a conditional service assertion + the PES-02 gate) will flip this to archive-ready.