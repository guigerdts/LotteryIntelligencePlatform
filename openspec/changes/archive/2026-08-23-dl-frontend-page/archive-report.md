# Archive Report — DL Frontend Page (`/dl`)

**Change**: `dl-frontend-page`
**Store**: `hybrid` (openspec filesystem + engram)
**Archived**: `2026-08-23`
**Archived to**: `openspec/changes/archive/2026-08-23-dl-frontend-page/`

## Purpose

Give the final `/api/v1/dl` backend a frontend surface: typed service client, Deep Learning page at `/dl` mirroring the ML Models page (skeleton/error/empty/data parity), manual train trigger with persistent busy state, lazy route + sidebar entry. Fully additive delivery; zero shared-layer delta (`apiClient`, `useApi`, existing pages untouched).

## Final State (at close, 2026-08-23)

Sources ranked per Final-State Authority: orchestrator final-state facts (launch prompt) > tasks.md/verify-report snapshots. Snapshot-derived claims are attributed to their time of writing.

### Delivery

| Item | Value |
|------|-------|
| PR | #64 (single PR; pre-approved split not exercised — deviation accepted and documented per verify-report §7a, ratified exception on the ~615 authored-line diff) |
| Commit | `9d97b93` on main — 12 files, +997 |
| GGA | PASSED |
| CI | green |
| vitest (merge-time record) | **150 passed / 150** across 22 files (~12 min); fresh focused run at verification time: 26/26 (DL 12 + App 6 + Sidebar 8), exit 0 |
| Ledger | native complete — attempt settled passed within the 1200 budget |

### Verification

Per `verify-report.md` at verification time (evidence revision main @ `9d97b93`): verdict **PASS WITH WARNINGS**, **0 CRITICAL**, **validator-admitted** — 6 requirements / 13 scenarios valid, 13/13 scenarios compliant (+1 R2 bonus case), zero UNTESTED/FAILING/PARTIAL. `tsc -b --force` exit 0. Zero shared-layer delta confirmed by diffstat review.

### Warnings — resolution status

| Warning (verify-report §7) | Status at close |
|----------------------------|-----------------|
| (c) `trainOutcome` not cleared on lottery switch → stale cross-lottery failure text until next successful train | **FOLLOW-UP RECORDED** (below) — NOT a defect of this change per verifier ruling: spec scenarios only cover post-train display; one-line gate fix candidate identified (`trainOutcome.lottery_id === selectedLotteryId`, field already present on `DLTrainResult`) |
| (d) task 4.3 checkbox unchecked though smoke executed post-merge | **RESOLVED AT ARCHIVE** — ticked under explicit orchestrator authorization with smoke evidence attached (see Task Completion Gate below) |

## Follow-ups (routed out of this change)

| # | Follow-up | Origin |
|---|-----------|--------|
| 1 | One-line `trainOutcome` lottery-gate fix: render failed-family rows only when `trainOutcome.lottery_id === selectedLotteryId` (or reset outcome in the selection effect) | verify-report warning (c) |
| 2 | `apiClient.parseResponse` cannot handle 304 empty body (unconditional `response.json()`) — blocks future ETag conditional requests | proposal Risks / verify context |
| 3 | `useApi` error-code flattening limits page-level error differentiation (root cause behind D1 null-mapping placement inside the capability service) | proposal Approach note |
| 4 | Window/cut form inputs deferred to v2 (v1 ships `window=10`, `cut=auto` defaults) | proposal Non-goals |
| 5 | Pre-existing CLI no-snapshot error-path quirks affecting ML+DL (inherited from prior change) | prior change carry-over |

## Spec Sync

- Delta spec: `openspec/changes/dl-frontend-page/specs/dl-frontend-page/spec.md` — all-ADDED capability, validator-admitted (6 requirements / 13 scenarios).
- No prior `dl-frontend-page` domain existed in `openspec/specs/` → house convention for NEW capabilities applies (verified pre-sync against three byte-identical precedents: `testing` via `diff -r` exit 0; `release-candidate` and `documentation` IDENTICAL).
- Synced to: **`openspec/specs/dl-frontend-page/spec.md`** — new main spec created as byte-identical mechanical copy (**DIFF-1**: empty, exit 0). 6 requirements added, 0 modified, 0 removed; no other main specs affected.

## Task Completion Gate

- tasks.md after reconciliation: **16/16 checked, 0 unchecked**.
- Archive-time reconciliation performed under explicit launch-prompt authorization ("tick it yourself citing that evidence — comment-only edit"), backed by verify-report proof:
  - **4.3 `[ ]` → `[x]`**: smoke was executed post-merge per orchestrator final-state facts — uvicorn :8000 + vite :5173 lifted; `curl localhost:5173/api/v1/dl/models?lottery_id=1` returned live DL JSON through the vite proxy; `GET /dl` served the SPA shell (title verified). Owner visual confirmation remains pending as an explicit note in the checkbox line; optional ~100 s real train intentionally skipped (idempotent fingerprint short-circuit already proven in `dl-snapshot-persistence`). Reason recorded: launch-prompt authorization + verify-report §7d evidence.
  - **4.1 count corrected**: "14 DL cases" → actual DL-local file holds 12 cases (13 change-new counting the App deep-link); merge-time full-suite record 150/150 cited. Reason recorded: verify-report §7(e) ruling "correct the count when ticking 4.3".
- Both edits are comment/checkbox-only; no requirement or scenario text altered.

## Mechanical Copy Readbacks (MANDATORY)

- **DIFF-1** (delta spec source vs `openspec/specs/dl-frontend-page/spec.md`): empty output, exit 0 — byte-identical.
- **DIFF-2** (pre-move recursive snapshot vs `openspec/changes/archive/2026-08-23-dl-frontend-page/`): empty output, exit 0 — byte-identical (archive-report.md excluded, additive-only — it did not exist in the snapshot).
- Move executed with plain `mv`; no git commands run per orchestrator constraint — edits left in worktree uncommitted. Source folder confirmed absent from `openspec/changes/` after the move.

## Gates

- **Native Review Receipt Gate**: no structured status with a `reviewGate` key was provided — structurally absent; archive proceeded under ordinary repository policy. No review topics read.
- **CRITICAL findings**: none in verify-report — no block.
- **Action Context Guard**: no `workspace-planning` mode, no `allowedEditRoots` restriction reported — filesystem archive operations permitted within repo.
- **Strict-vs-OpenSpec policy**: archive ran with complete artifacts (proposal, design, delta spec, tasks, verify-report) and fully reconciled tasks; no partial-archive override needed.

## Artifacts Read (traceability)

Filesystem (openspec side of hybrid mode):
- `openspec/changes/dl-frontend-page/proposal.md`
- `openspec/changes/dl-frontend-page/design.md`
- `openspec/changes/dl-frontend-page/specs/dl-frontend-page/spec.md` (mechanical copy only — bytes never routed through model)
- `openspec/changes/dl-frontend-page/tasks.md`
- `openspec/changes/dl-frontend-page/verify-report.md`
- `openspec/config.yaml`, `openspec/changes/archive/2026-08-20-fase-17-testing/archive-report.md` (house format/convention precedent)

Engram side: archive-report persisted as `sdd/dl-frontend-page/archive-report`.

## Artifacts Archived

- `openspec/changes/archive/2026-08-23-dl-frontend-page/proposal.md`
- `openspec/changes/archive/2026-08-23-dl-frontend-page/design.md`
- `openspec/changes/archive/2026-08-23-dl-frontend-page/specs/dl-frontend-page/spec.md`
- `openspec/changes/archive/2026-08-23-dl-frontend-page/tasks.md` (16/16)
- `openspec/changes/archive/2026-08-23-dl-frontend-page/verify-report.md`
- `openspec/changes/archive/2026-08-23-dl-frontend-page/archive-report.md` (this file, additive)

## What Changed

- Main spec created: `openspec/specs/dl-frontend-page/spec.md`
- Change folder moved to `openspec/changes/archive/2026-08-23-dl-frontend-page/`
- tasks.md reconciled (4.3 ticked with smoke evidence; 4.1 count corrected)

## What Did NOT Change

- No production code, tests, or shared-layer files modified. Nothing committed or pushed (orchestrator instruction: leave edits in worktree, no git commands).
- Archived artifacts are immutable — never modify them.

## Notes

- Owner visual confirmation of `/dl` in a real browser is the only outstanding human step; curl-level runtime proof is on record (see Task Completion Gate). Tracked under follow-up visibility, not a gate.
- The optional ~100 s real train smoke was deliberately skipped: its risk domain (snapshot fingerprint idempotent short-circuit) was proven during `dl-snapshot-persistence`.
