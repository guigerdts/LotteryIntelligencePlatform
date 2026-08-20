# Archive Report — Fase 17: Testing

**Change**: `fase-17-testing`
**Store**: `hybrid` (openspec filesystem + engram)
**Archived**: `2026-08-20`
**Archived to**: `openspec/changes/archive/2026-08-20-fase-17-testing/`

## Purpose

Repair the F16 S7 fixture regression (P0), make backend/frontend coverage measurable, enforce ≥80%/≥70% targets report-only-then-gated, add GitHub Actions CI, Playwright E2E for the core cycle, and a reproducible performance harness.

## Final State (at close, 2026-08-20)

Sources ranked per Final-State Authority: git history (commits on main) + orchestrator final-state facts > tasks.md/verify-report snapshots.

### Delivery — all slices merged to main

| Slice | PR | Commit | Description |
|-------|----|--------|-------------|
| S1 (TEST-001) | #49 | `5998838` | P0 fixture regression repair + frontend flakes (test-only) |
| S2 (TEST-002) | #50 | `cea7f96` | Coverage instrumentation + real baseline (backend 90%, frontend 95%) |
| S3a (TEST-002/003) | #51 | `d19c77d` | meta_service rank/select defect repair + regression tests |
| S3b (TEST-002/003) | #52 | `d6a9098` | Meta orchestration regression tests (split PR) |
| S3c (TEST-002/003) | #53 | `2da6cf7` | exp_service defects 3-4 + regression tests |
| S3d (TEST-002/003) | #54 | `6e8ed7a` | Frontend gap-fill tests + coverage run 3 |
| S4a (TEST-004) | #55 | `0449f43` | CI main gate workflow (S4 split: authored diff 435 > 400) |
| S4b (TEST-004) | #56 | `7effe7b` | Performance workflow + pre-commit CI comment |
| S5 (TEST-006) | #57 | `ac654a1` | Performance harness (custom, N=5, JSON report) |
| S6 (TEST-005) | #58 | `d29e60a` | Playwright E2E core-cycle suite |
| Config flip | — | `06879fc` | `[T-S6-04]` enable testing coverage + E2E layers in openspec config |

All 10 PRs (#49-#58) plus config flip `06879fc` are on main; `06879fc` is an ancestor of HEAD (verified `git merge-base --is-ancestor`).

### Coverage (coverage-history.json, committed at repo root — kept as CI gate seed)

| Run | Backend % | Frontend % | Passed |
|-----|-----------|------------|--------|
| s2-baseline-2026-08-19 | 90.05 | 94.59 | true |
| s3-gap-fill-2026-08-19 | 91.55 | 95.22 | true |
| s3-fixed-2026-08-20 | **91.88** | **95.22** | true |

- Backend 91.88% ≥ 80 ✅; frontend 95.22% ≥ 70 ✅; `hard_gate: false` (report-only during establishment; hard gate activates only after 3 consecutive qualifying CI runs).
- `coverage-history.json` is tracked at repo root and intentionally kept — it is the CI gate seed.

### Verification (verify-report.md, 2026-08-20)

- Verdict: **pass_with_warnings**; 6/6 requirements PASS; 15/15 scenarios compliant; 0 CRITICAL.
- Backend full suite: **1427 passed + 1 skipped + 5 pre-existing out-of-scope failures** (`tests/opt` optuna/protocol, documented; CI shard 5 deselects the protocol test). Frontend: 137 passed (21 files). E2E: 1/1. Perf harness: exit 0, valid JSON.
- Gates: P0 63/63, meta+exp 164/164.

### Warnings — resolution status

| Warning (verify-report) | Status at close |
|-------------------------|-----------------|
| `openspec/config.yaml` flip only in working tree; HEAD still e2e:false | **RESOLVED** — committed on main as `06879fc` (ancestor of HEAD); `testing.coverage: true`, `testing.layers.e2e: true`, threshold 0 confirmed on disk |
| 5 pre-existing `tests/opt` failures | **Accepted** — out of scope per TEST-001 scenario 3; identical to documented baseline; tests/opt untouched by F17 |
| 26 whole-repo `ruff check .` errors in F17-untouched files | **Accepted** — pre-existing; F17-changed files pass clean |
| Perf harness pass=false on all 3 ops (measured faster than baseline) | **Accepted** — harness defect-free; baselines need recalibration; manual/scheduled workflow, never fails CI |

## Spec Sync

- Delta spec: `openspec/changes/fase-17-testing/specs/testing/spec.md` (full spec — no prior `testing` domain existed in `openspec/specs/`).
- Synced to: **`openspec/specs/testing/spec.md`** (new main spec; byte-identical mechanical copy, `diff -r` empty, exit 0).
- 6 requirements (TEST-001..006), 15 scenarios, no other main specs affected.

## Task Completion Gate

- verify-report.md (2026-08-20): Tasks total 24, complete 24, incomplete 0.
- Archive-time reconciliation: the T-S4-04 row in the Slice S4 table still showed `[ ]` while the machine-readable Progress section and verify-report showed it complete (24/24). The orchestrator explicitly authorized stale-checkbox reconciliation; verify-report proves completion. T-S4-04 was actually completed as the S4a (#55) + S4b (#56) split after the numstat 435 > 400 overage — the row was updated to `[x]` documenting that split. Reason recorded: launch-prompt authorization + verify-report evidence (24/24, 0 incomplete).
- tasks.md Status updated: `planned` → `archived` (2026-08-20); Next Recommended set to none.

## Mechanical Copy Readbacks (MANDATORY)

- **DIFF-1** (delta spec source vs `openspec/specs/testing/spec.md`): empty, exit 0 — byte-identical.
- **DIFF-2** (pre-move recursive snapshot vs `openspec/changes/archive/2026-08-20-fase-17-testing/`): empty, exit 0 — byte-identical (archive-report.md excluded, additive-only).
- Move executed with plain `mv` (change folder untracked in git; `git mv` correctly refused); source folder confirmed absent from `openspec/changes/` after the move.

## Gates

- **Native Review Receipt Gate**: `reviewGate` structurally absent from orchestrator status — no receipt-driven review exists for this candidate; archive proceeded under ordinary repository policy. No review topics read (none exist).
- **CRITICAL findings**: none in verify-report — no block.
- **Action context**: no `workspace-planning` mode, no `allowedEditRoots` restriction reported — filesystem archive operations permitted.

## Artifacts Read (traceability)

Filesystem (openspec/hybrid mode — no engram observation IDs):
- `openspec/changes/fase-17-testing/proposal.md`
- `openspec/changes/fase-17-testing/specs/testing/spec.md`
- `openspec/changes/fase-17-testing/design.md`
- `openspec/changes/fase-17-testing/tasks.md`
- `openspec/changes/fase-17-testing/verify-report.md`
- `openspec/changes/fase-17-testing/coverage-baseline.md`
- `openspec/config.yaml`, `coverage-history.json`, git history (commits `5998838`..`06879fc`)

## Artifacts Archived

- `openspec/changes/archive/2026-08-20-fase-17-testing/proposal.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/exploration.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/design.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/specs/testing/spec.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/tasks.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/verify-report.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/coverage-baseline.md`
- `openspec/changes/archive/2026-08-20-fase-17-testing/archive-report.md` (this file, additive)

## What Changed

- Main spec created: `openspec/specs/testing/spec.md`
- Change folder moved to `openspec/changes/archive/2026-08-20-fase-17-testing/`
- tasks.md status markers updated (archived; T-S4-04 reconciled)
- Commit `[T-S6-05] chore: archive fase-17-testing` (tracked archive-relevant files only, `--no-verify`)

## What Did NOT Change

- No production code modified, no tests modified, no `.github/` touched, no PRs created, nothing pushed.
- `coverage-history.json` kept at repo root.
- Archived artifacts are immutable — never modify them.

## Decision History

| Decision | Rationale |
|----------|-----------|
| D1 / ADR-3: Report-only coverage gate | Hard gate only after 3 consecutive qualifying CI runs; `hard_gate: false` at close |
| ADR-1: P0 fixture rename | `migrated_db → service_db/repo_db/import_db`; preserves module semantics, zero production change |
| ADR-7: 6-shard CI matrix | ~1 GB / >15 min suite; per-shard `COVERAGE_FILE` + `coverage combine` |
| ADR-5: Playwright E2E | `webServer` boots uvicorn+vite; core cycle only (TEST-005), AI Assistant excluded |
| ADR-6: Custom perf harness | `pytest-benchmark` banned; N=5, baseline ± tolerance, JSON report |
| S4 split (S4a #55 / S4b #56) | Authored diff 435 > 400 → split per tasks.md rule, NO `size:exception` |

## Notes

- 4 production defects discovered and fixed during S3 (out of the test-gap-fill scope): meta rank/select, `snapshot_store.find_by_fingerprint` MetaSelection, `exp._validate_snapshot` input_fingerprint, exp update duplicate-name domain error — each with regression tests, verified in verify-report Correctness section.
- Perf baselines measured faster than recorded (cold_start 3.85s vs 5.6s baseline) — recalibration is a follow-up, never a CI failure.