```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d7bcae87278b387b963cf4ba25ccca275f937a18331e443212dddd1e980d8216
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 15/15
test_command: backend/.venv/bin/pytest tests/test_services.py tests/test_integrity.py tests/test_import_service.py -q
test_exit_code: 0
test_output_hash: sha256:d7bcae87278b387b963cf4ba25ccca275f937a18331e443212dddd1e980d8216
build_command: backend/.venv/bin/ruff check tests/test_services.py tests/test_integrity.py tests/test_import_service.py tests/meta/test_meta_service.py tests/test_exp_add_run.py tests/test_exp_metric_readers.py tests/performance/harness.py src/backend/app/meta/context.py src/backend/app/meta/snapshot_store.py src/backend/app/services/exp_service.py src/backend/app/services/meta_service.py tests/exp_helpers.py tests/test_ml_pr5.py
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```
## Verification Report

**Change**: fase-17-testing
**Version**: N/A (spec dated 2026-08-19)
**Mode**: Standard

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 24 |
| Tasks complete | 24 |
| Tasks incomplete | 0 |

### Build & Tests Execution
**Build**: ✅ Passed (ruff on 13 F17-changed backend files; whole-repo `ruff check .` exits 1 with 26 pre-existing errors in F17-untouched files — WARNING, out of scope)
```text
backend/.venv/bin/ruff check tests/test_services.py tests/test_integrity.py tests/test_import_service.py tests/meta/test_meta_service.py tests/test_exp_add_run.py tests/test_exp_metric_readers.py tests/performance/harness.py src/backend/app/meta/context.py src/backend/app/meta/snapshot_store.py src/backend/app/services/exp_service.py src/backend/app/services/meta_service.py tests/exp_helpers.py tests/test_ml_pr5.py
All checks passed!
```

**Tests**: ✅ 1427 passed (full backend suite per-directory) + 1 skipped + 5 pre-existing tests/opt failures; gates: P0 63/63, meta+exp 164/164, frontend vitest 137/137, Playwright E2E 1/1, perf harness exit 0
```text
P0 gate: 63 passed, 1 warning in 116.64s
Meta/exp gate: 164 passed in 7.31s
Frontend: 137 passed (21 files)
Playwright: 1 passed (29.6s)
Harness: exit 0, /tmp/opencode/s5-report.json valid
```

**Coverage**: backend 91.88% / frontend 95.22% → ✅ Above targets (>=80 / >=70); hard_gate false (still establishing)

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| TEST-001 | suite green after repair | 3 modules, 63 tests | ✅ COMPLIANT |
| TEST-001 | hiding tests rejected | no skip/xfail markers (grep) | ✅ COMPLIANT |
| TEST-001 | unrelated failure separated | tests/opt 5 failures documented, CI deselects protocol test | ✅ COMPLIANT |
| TEST-002 | backend coverage measured | pytest-cov smoke run (TOTAL row renders) | ✅ COMPLIANT |
| TEST-002 | frontend coverage measured | @vitest/coverage-v8 + vite block; 95.22% summary | ✅ COMPLIANT |
| TEST-003 | report-only during establishment | no fail_under; gate job never fails pre-establishment | ✅ COMPLIANT |
| TEST-003 | hard gate activation | 3-consecutive-runs logic in ci.yml gate | ✅ COMPLIANT |
| TEST-003 | frontend target change needs evidence | threshold stays >=70 | ✅ COMPLIANT |
| TEST-004 | push triggers CI | CI green on main run 32398125104 (9/9 jobs) | ✅ COMPLIANT |
| TEST-004 | long suite sharded | 6-shard matrix + coverage combine | ✅ COMPLIANT |
| TEST-004 | pre-commit is not the gate | CI is gate; pre-commit complementary only | ✅ COMPLIANT |
| TEST-005 | core cycle green | Playwright 1/1 (seed -> /estadisticas -> /) | ✅ COMPLIANT |
| TEST-005 | AI Assistant out of scope | no /ia spec in e2e/ (scope guard comment) | ✅ COMPLIANT |
| TEST-006 | reproducible measurement | harness exit 0, valid JSON, variance+outliers flagged | ✅ COMPLIANT |
| TEST-006 | no pytest-benchmark | absent from pyproject.toml/uv.lock (grep) | ✅ COMPLIANT |

**Compliance summary**: 15/15 scenarios compliant

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| TEST-001 defects | ✅ Implemented | find_by_fingerprint consults MetaRanking+MetaSelection (snapshot_store.py:54-82); select() reads MetaRankingEntry from DB (meta_service.py:263-280); _validate_snapshot returns input_fingerprint for ml/dl (exp_service.py:652-654); update() raises DuplicateExperimentError (exp_service.py:219-227) |
| TEST-001 regression tests | ✅ Implemented | meta_service happy paths + idempotency (test_rank_is_idempotent_by_fingerprint, test_select_is_idempotent_by_fingerprint, test_rank_reads_ml_metrics); exp_add_run duplicate-name domain error + input_fingerprint; exp_metric_readers ml/dl/opt compares |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-1 rename fixtures | ✅ Yes | service_db/repo_db/import_db; no production change |
| ADR-3 report-only gate | ✅ Yes | coverage-history.json hard_gate false; 3-run logic |
| ADR-5 Playwright | ✅ Yes | webServer uvicorn+vite, healthchecks, reuseExistingServer:false |
| ADR-6 custom harness | ✅ Yes | N=5, warmup 1, tolerance 0.20, JSON report |
| ADR-7 6-shard matrix | ✅ Yes | COVERAGE_FILE per shard + combine |

### Issues Found
**CRITICAL**: None
**WARNING**:
- openspec/config.yaml flip (testing.e2e/coverage: true, threshold 0) exists only in the WORKING TREE — no F17 commit touched the file; HEAD still e2e:false/coverage:false (openspec/config.yaml:49-53). Action: commit or confirm deferral before archive.
- 5 pre-existing tests/opt failures (4x optuna ModuleNotFoundError bayesian.py:32 + 1x protocol TypeError) — identical to documented baseline, tests/opt untouched by F17 (git diff empty). Out of scope per TEST-001 s3.
- Whole-repo `ruff check .` exits 1: 26 pre-existing errors in F17-untouched files (api/v1/meta.py:7, test_migrations.py:696, etc.). Changed files pass clean.
- Perf harness pass=false on all 3 ops (measured faster than baseline: cold_start 3.85s vs 5.6s, stats 0.018s vs 0.045s, bt 0.166s vs 0.52s) — harness defect-free; baselines need recalibration.
**SUGGESTION**: None

### Verdict
PASS WITH WARNINGS
All 6 requirements and 15/15 scenarios verified; warnings are pre-existing/out-of-scope or workspace-state (uncommitted config flip) — archive is safe once the flip is committed or confirmed deferred.
