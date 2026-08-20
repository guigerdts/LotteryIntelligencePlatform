# Proposal: Fase 17 — Testing

## Intent

F16 S7 left a regression: 63 backend tests error with `ScopeMismatch` (session-scoped `migrated_db` shadowed by function-scoped fixtures in 3 modules); repair first (P0). F17 builds the roadmap testing phase (5 types, ≥80% backend / ≥70% frontend): no CI, coverage, browser E2E, or perf tooling.

## Scope

**In**
- P0: repair fixture regression (`test_services.py` ×31, `test_integrity.py` ×20, `test_import_service.py` ×12) + 3 failing frontend tests; full suite green.
- Coverage: `pytest-cov` + `[tool.coverage]`; `@vitest/coverage-v8`; real baseline; REPORT-ONLY gate (D1).
- GitHub Actions CI (D5), sharded for suite runtime.
- Playwright E2E core cycle: create lottery → import draws → generate stats → dashboard (D3).
- Perf harness: repeated runs, baseline/target/tolerances; no pytest-benchmark (D4).

**Out**
- AI Assistant E2E; lowering frontend target (D2); pytest-benchmark; Fase 18/19; production changes for the fixture issue; hard gate (until 3 consecutive runs).

## Capabilities

**New** — `testing-infrastructure`: coverage policy (report-only → hard gate after 3 runs), measurement config, CI gates, Playwright core cycle, perf-harness contract.
**Modified** — None (no spec governs testing); `openspec/config.yaml` flags (`coverage:false`, `e2e:false`, `coverage_threshold:0`) update as config.

## Approach

Exploration's fix-and-measure: (1) P0 repair → green suite; (2) instrument + baseline; (3) fill biggest gaps; (4) CI report-only gate; (5) perf harness; (6) E2E last.

## Affected Areas

| Area | Impact |
|---|---|
| `backend/tests/conftest.py` + 3 test modules | Modified — P0 fixture fix |
| `backend/pyproject.toml` | Modified — pytest-cov, coverage config |
| `frontend/package.json`, `vite.config.ts`, History/Networks tests | Modified — coverage-v8; 3 failing tests |
| `.github/workflows/` | New — CI |
| `frontend/e2e/`, `backend/tests/performance/` | New — E2E, perf harness |
| `openspec/config.yaml` | Modified — flags |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Frontend ≥70% unreachable | Med | Report-only; evidence before change (D2) |
| Suite >15 min / ~1 GB peak in CI | High | Directory sharding; PR subset |
| Browser E2E largest slice | Med | Core cycle only (D3) |
| New deps (pytest-cov, coverage-v8, Playwright) | Certain | Record in tasks |
| Broken tests contradict F16 DoD | Certain | Recorded inconsistency; P0 first |

## Rollback Plan

- Revert conftest + module fixture changes (P0); remove coverage deps; delete workflow files; remove `frontend/e2e/` + Playwright config and `backend/tests/performance/`; revert config flags.

## Dependencies

- New dev deps: `pytest-cov`, `@vitest/coverage-v8`, `@playwright/test`. Green suite before baseline.

## Success Criteria

- [ ] Full backend suite green; nothing excluded/xfailed.
- [ ] Backend + frontend coverage measured and recorded.
- [ ] Report-only gate live; 3-run stabilization path for hard gate.
- [ ] E2E core cycle green in CI.
- [ ] Perf harness reproducible (baseline/target/tolerances).
