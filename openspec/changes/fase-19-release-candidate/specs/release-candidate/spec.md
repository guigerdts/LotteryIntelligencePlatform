# Spec — fase-19-release-candidate

**Date**: 2026-08-21
**Source**: proposal.md (8 slices, owner-approved scope) + exploration.md evidence
**Convention**: requirements RC-001..RC-010; each maps to roadmap checklist items.

## Requirements

### RC-001 — Dependency reconciliation (S0)
The backend virtualenv MUST match the runtime dependencies declared in `pyproject.toml` (`deap==1.4.1`, `optuna`), and `uv.lock` MUST be regenerated consistently with `pyproject.toml`.

**Scenarios**
- (a) `backend/.venv/bin/python -c "import optuna, deap"` succeeds.
- (b) Full backend suite from `backend/`: **0 failed** (the 5 tests/opt ModuleNotFoundError failures are eliminated by installation, NOT by skip/xfail/assertion weakening).
- (c) `uv.lock` timestamp ≥ `pyproject.toml` timestamp and consistent with declared deps.

### RC-002 — Frontend stability under load (S1)
The flaky frontend tests identified in exploration (`App.test.tsx` router navigation, `Experiments.test.tsx` skeleton placeholders, `History.test.tsx` pagination) MUST be stabilized by removing nondeterminism (proper async waits / deterministic fixtures). Fixes MUST NOT be sleep-hacks, skipped tests, or weakened assertions.

**Scenarios**
- (a) Full frontend vitest suite passes completely in **3 consecutive runs**.
- (b) The 3 previously-flaky test files contain no added arbitrary sleeps masking races; diffs show wait/determinism fixes.
- (c) Root cause of each flake documented (introduced defect vs pre-existing race).

### RC-003 — Release audit with existing gates (S2)
A release audit MUST be executed using the gates that exist in the repo (ruff, pytest, vitest, playwright, coverage config). Tooling not present in the repo (e.g., mypy/bandis if unconfigured) is recorded as post-1.0 debt, NOT installed ad-hoc. Findings MUST be classified: critical / major / minor / pre-existing-debt / environment / harness.

**Scenarios**
- (a) Audit report artifact exists listing every gate run, its result, and classified findings.
- (b) No new linter/type-checker is added to CI or manifests during F19.
- (c) Every finding names its class per operational rule 9.

### RC-004 — Critical audit fixes (S3)
Findings classified critical or major by RC-003 MUST be fixed when the fix is local, objective, and does not change contract/architecture. Non-critical pre-existing debt MUST NOT be fixed incidentally.

**Scenarios**
- (a) Each critical/major finding is either fixed (with commit + re-run evidence) or explicitly deferred with justification in the audit report.
- (b) Affected suites re-run green after fixes.

### RC-005 — Performance validation (S4)
The `cold_start` signal (~13–17 s measured vs ~5.6 s baseline estimate) MUST be investigated to determine: real regression, harness problem, or justifiable change. Recalibration happens ONLY with evidence. Results MUST be reproducible.

**Scenarios**
- (a) Investigation evidence exists (import-graph measurement, harness methodology check).
- (b) A verdict is documented: regression-fixed | harness-artifact-documented | baseline-recalibrated-with-evidence.
- (c) Final harness run produces a report artifact; exit contract respected (regressions are data, not gate failures).

### RC-006 — Functional release validation (S5)
A full functional validation session MUST be executed and recorded in `RELEASE_VALIDATION.md` with REAL commands and outputs: backend suite, frontend suite, E2E Playwright, coverage numbers. No invented criteria or results.

**Scenarios**
- (a) RELEASE_VALIDATION.md exists with dated command transcripts (or exact commands + summarized verified outputs).
- (b) Backend 0 failed; frontend 0 failed (post-RC-002); E2E pass; coverage reported against F17 baselines (backend ~91.88%, frontend ~95.22%).

### RC-007 — Release freeze (S6)
Version MUST move 0.1.0 → 1.0.0 in both manifests (`backend/pyproject.toml`, `frontend/package.json`); tag `v1.0.0-rc.1` MUST be created; PROJECT_STATUS.md MUST record the real RC state.

**Scenarios**
- (a) Both manifests show 1.0.0; no other version strings contradict.
- (b) Git tag `v1.0.0-rc.1` exists on the freeze commit.
- (c) PROJECT_STATUS.md shows F19 state and freeze meaning (fixes only until release).

### RC-008 — Changelog and release notes (S7)
`CHANGELOG.md` MUST be generated from real git history (phase tags + PR-sized commits), and release notes prepared. Content MUST trace to actual commits.

**Scenarios**
- (a) CHANGELOG.md covers F1→F19 milestones traceable to git log/tags.
- (b) Release notes draft exists for v1.0.0.

### RC-009 — LICENSE owner decision (S7, PARKED)
The LICENSE file choice is the SINGLE owner decision of F19. Work stops at the point S7 requires it; nothing else blocks on it.

**Scenarios**
- (a) No LICENSE file is created without explicit owner choice.
- (b) When reached, the orchestrator presents problem/evidence/options/recommendation and STOPS.

### RC-010 — Evidence integrity (transversal)
No failure may be hidden via skip, xfail, or assertion weakening during F19. Every release claim cites a reproducible command. Debt classification follows operational rule 9 everywhere.

**Scenarios**
- (a) Diff review of F19 commits shows no new skips/xfails/weakened assertions (pre-existing ones unchanged).
- (b) RELEASE_VALIDATION.md and audit report cite runnable commands.
