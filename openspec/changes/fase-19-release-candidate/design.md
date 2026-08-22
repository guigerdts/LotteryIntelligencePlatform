# Design — fase-19-release-candidate

**Date**: 2026-08-21
**Inputs**: proposal.md, specs/release-candidate/spec.md

## Approach per slice

### S0 — Dependency reconciliation
- Check `uv` availability. If present: `uv lock` (or `uv sync`) from `backend/` to regenerate `uv.lock` against current `pyproject.toml`. If absent: `backend/.venv/bin/pip install -e ".[dev]"` equivalent + document lock regeneration command for owner (lock file is a build artifact; the CONTRACT is pyproject).
- Install exactly what pyproject declares: `deap==1.4.1`, `optuna` (version as declared). No version bumps beyond declarations.
- Gate: full backend suite from `backend/` → 0 failed.
- Classification note: the 5 failures are **environment problem** (deps declared but never installed), not product defects.

### S1 — Frontend stability
- Reproduce: 2–3 full vitest runs; capture which tests drop and their error shapes (timeout vs assertion).
- Inspect the 3 files for async patterns: missing `waitFor`/`findBy*`, race between MSW handlers and assertions, router navigation timing, pagination double-effects.
- Fix by removing nondeterminism: `await findBy*`, explicit act waits, deterministic MSW fixtures. NO arbitrary sleeps; NO test.skip.
- Gate: `npm test -- --run` fully green ×3 consecutive.

### S2 — Release audit
- Run existing gates and record outputs:
  - `backend/.venv/bin/ruff check .`
  - backend pytest full (+ coverage if configured)
  - frontend vitest full
  - Playwright E2E (`npx playwright test`) if environment allows (browser install check first)
  - grep hygiene: secrets patterns, print/debug leftovers, console.log in src
- Check whether mypy/bandit are configured anywhere (pyproject, CI workflows). Expected: NOT configured → record as post-1.0 debt per spec RC-003(b), do NOT install.
- Output: `openspec/changes/fase-19-release-candidate/audit-report.md` with findings classified per rule 9.

### S3 — Critical fixes
- Only critical/major findings from audit-report.md. Each fix = own commit `[T-S3-xx] fix: ... — RC-004`.
- Deferred items get justification lines in audit report.

### S4 — Performance validation
- Read harness methodology (`harness.py` docstring + config.yaml): cold_start = fresh-interpreter import of backend.app.main + create_app().
- Measure import graph: `python -X importtime -c "from backend.app.main import create_app"` style run; identify heavy imports (torch/sklearn lazy per DLE-17 — verify still true).
- Compare box noise: repeat runs; check whether 13–17 s is stable or swinging.
- Verdict paths:
  - Real regression → locate + fix if local/objective.
  - Harness/estimate artifact (e.g., baseline was a design guess, cold start includes torch CPU init) → recalibrate config.yaml baselines with measured evidence + comment.
- Evidence: perf report JSON + investigation notes appended to audit report or dedicated section.

### S5 — Functional validation
- One clean session: backend suite, frontend suite ×1 (post-S1), E2E, coverage.
- Write `RELEASE_VALIDATION.md` at repo root: date, HEAD sha, exact commands, outcomes, coverage numbers vs F17 baselines.

### S6 — Freeze
- Bump versions: `backend/pyproject.toml` version="1.0.0"; `frontend/package.json` "version": "1.0.0" (+ regenerate frontend lockfile version field if it embeds version).
- PROJECT_STATUS.md: F19 row → RC state; freeze statement (fixes only until v1.0.0).
- Commit `[T-S6-xx] chore: release freeze 1.0.0-rc.1 — RC-007`; tag `v1.0.0-rc.1` on that commit; push with tag.

### S7 — Changelog / release notes
- Generate CHANGELOG.md from git log grouped by phase tags (fase-N-* tags exist through fase-5; later phases via commit ranges from PROJECT_STATUS dates).
- Release notes draft: `docs/releases/v1.0.0-rc.1.md` (or RELEASE_NOTES.md at root — decide by repo convention: none exists yet → root RELEASE_NOTES.md).
- LICENSE: STOP and ask owner (RC-009) when this point is reached.

## Delivery
- stacked-to-main, auto-chain; ≤400 lines/PR per slice; conventional commits `[T-Sx-yy] ... — RC-00N`; `--no-verify`; `git restore .atl` before staging.

## Verification mapping
- RC-001→S0 gate; RC-002→S1 gate; RC-003/004→S2/S3 artifacts+commits; RC-005→S4 evidence; RC-006→RELEASE_VALIDATION.md; RC-007→manifests+tag; RC-008→CHANGELOG; RC-009→stop-and-ask event; RC-010→diff review at verify.
