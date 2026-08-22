# Proposal — fase-19-release-candidate

**Date**: 2026-08-21
**Status**: draft
**Roadmap**: `IMPLEMENTATION_ROADMAP.md:384-394` — final phase of the chain.
**Exploration**: `openspec/changes/fase-19-release-candidate/exploration.md`

## Why

F18 Documentation closed with the repo fully documented against real code (14 PRs, DOC-001..010 PASS). The roadmap has exactly one phase left: Release Candidate. Its job is to convert "works on my machine" into auditable v1.0 evidence: clean audit, zero critical defects, functional and performance validation runs, a feature freeze, and release artifacts.

## Problem statement

The codebase is feature-complete and well-tested (backend 1429 passed, ruff clean, 0 TODO markers) but NOT release-ready:

1. **Backend suite is red**: 5 tests/opt failures caused by `optuna` missing from the venv although `pyproject.toml:41-48` declares it (with `deap==1.4.1`) as the only permitted runtime deps for the opt engines. The lockfile (`uv.lock`, 2026-08-09) predates the dependency declarations (2026-08-19).
2. **Frontend suite is flaky under load**: full-suite vitest runs drop 1–3 timing-sensitive tests (`App.test.tsx` router nav, `Experiments.test.tsx` skeleton, `History.test.tsx` pagination); all pass in isolation. A release cannot claim "all green" on a flaky suite.
3. **Performance evidence is unresolved**: the F17 harness flags `cold_start` FAIL (~13–17 s measured vs 5.6 s design estimate). Nobody has investigated or recalibrated.
4. **Release artifacts missing**: versions stuck at 0.1.0 in both manifests, no semver git tags, no CHANGELOG, no LICENSE (owner decision parked since F18), no freeze statement.

## Proposed approach — 8 slices

| Slice | Goal | Key evidence gate |
|---|---|---|
| **S0 — Dependency reconciliation** | Install declared deps (`deap==1.4.1`, `optuna`) into backend/.venv; regenerate `uv.lock` consistently with `pyproject.toml`. | Backend suite: **0 failed** (the 5 optuna failures disappear mechanically). |
| **S1 — Flaky test stabilization** | Fix timing races in the 3 identified frontend test files (proper async waits, deterministic fixtures). | Full frontend suite green **3 consecutive runs**. |
| **S2 — Code audit** | Systematic audit with EXISTING gates (ruff, pytest, vitest, playwright, coverage) + manual review checklist (security hygiene, dead code, error handling, secrets). New tooling (mypy/bandit) is OUT — recorded as post-1.0 debt instead. | Audit report artifact with findings classified critical/major/minor. |
| **S3 — Critical fixes** | Fix whatever S2 classifies critical/major. Objective fixes only; anything architectural goes to debt register. | Re-run of affected suites green. |
| **S4 — Performance validation** | Run the F17 harness; investigate the cold_start signal (lazy-import audit of the app graph); either fix a real regression or recalibrate the baseline with measured evidence. | Perf report artifact; cold_start verdict documented (fixed OR recalibrated-with-evidence). |
| **S5 — Functional validation** | Full green sweep: backend suite, frontend suite, E2E, coverage numbers confirmed. Produce `RELEASE_VALIDATION.md` with actual commands + outputs. | All suites green in one documented session. |
| **S6 — Feature freeze** | Bump both manifests 0.1.0 → 1.0.0; tag `v1.0.0-rc.1`; freeze statement in PROJECT_STATUS.md (what freeze means: no new features, fixes only until release). | Tag exists; manifests consistent; freeze documented. |
| **S7 — Release prep** | Generate `CHANGELOG.md` from git history (objective); final docs consistency pass; release notes. LICENSE file: **PARKED on owner decision** (see below). | CHANGELOG covers F1→F19; docs consistent. |

## Out of scope

- New tooling (mypy, bandit, semgrep) — post-1.0 debt.
- Mounting the DL router (by-design boundary, documented).
- Perf harness re-architecture (harness stays as-is; only baselines/investigation).
- Any new features (this is the freeze phase).

## Open owner decision (parked, non-blocking until S7)

**LICENSE file choice.** Evidence: no LICENSE exists; CONTRIBUTING.md §8 documents the absence; a public v1.0 normally ships one. This is a legal/product choice that cannot be resolved from repo evidence. Options will be presented when S7 runs; everything else proceeds independently.

## Risks

- Installing optuna/deap pulls large trees into the venv; uv.lock regeneration must be verified reproducible.
- Flaky-test fixes can mask real races if done as sleep-hacks — fixes must remove nondeterminism, not wait longer.
- cold_start investigation may surface a real import-graph problem late in the cycle; mitigation: S4 runs before freeze (S6).

## Review workload forecast

Estimated total < 400 changed lines across slices (docs + small test fixes + manifest bumps); each slice is its own PR-sized unit. Chained delivery stacked-to-main per session preflight.
