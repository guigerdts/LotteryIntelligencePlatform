# Archive Report — DL Snapshot Persistence (`dl-snapshot-persistence`)

**Change**: `dl-snapshot-persistence`
**Store**: `openspec` (file-based)
**Closed**: `2026-08-23`
**Archived to**: closed IN PLACE at `openspec/changes/dl-snapshot-persistence/` — intentionally NOT moved to `openspec/changes/archive/` (see Closure Disposition)

## Purpose

Deliver the persistence/service/surface layer mandated by spec for deep-learning training: a flush-only `DlSnapshotStore` mirroring the ML store, an atomic `DlService` train flow (placeholder → train mlp→lstm → fill header → Decimal metrics → weight rows → retire old active → single commit; failure path leaves only a terminal failed header), CLI group `lip dl {train,models,metrics}`, API router `/dl/{train,models,metrics}` with ETag/304 parity, the spec-mandated engine fix threading real `cut` into `compute_dl_fingerprint`, and stale-citation cleanup. No schema migrations; INSERT-only writer against existing DDL.

## Closure Disposition (house-convention check, explicit)

Prior archive survey (14 folders in `openspec/changes/archive/`, 2026-08-06 … 2026-08-21):

- Dominant house convention closes a change by MOVING its folder to `archive/YYYY-MM-DD-{change-name}/`. 13 of 14 archived `tasks.md` files carry **no** status-marker line; only `2026-08-20-fase-17-testing/tasks.md` has one (`Status: **archived** · ...`). A status marker is therefore NOT a required house convention for closure.
- The orchestrator directed NO move for this change because `verify-report.md` path stability matters downstream.
- Per the launch rule ("add a status marker ONLY if prior conventions require it; if unsure, leave structure untouched"), the change-folder structure is left UNTOUCHED except for this additive report. **This report is the closure record**: the change is CLOSED and must be treated as completed history despite living outside `archive/`.

## Final State (at close, 2026-08-23)

Sources ranked per Final-State Authority: launch-prompt final-state facts > persisted `tasks.md` > `verify-report.md` (snapshot at verification time, evidence revision `sha256:381f04de…`, main @ `68d4640`).

### Delivery — all slices merged to main (chained-PR strategy, all rebase-merged)

| Slice | PR | Commit(s) | Description |
|-------|----|-----------|-------------|
| 1 | #59 | `ec9fbc7` + `0dae45e` | Engine cut-threading (`train(..., *, cut)` → fingerprint; `TrainResult.cut`; objective passes declared cut) |
| 2 | #60 | `6249877` | `DlSnapshotStore` (~+700 lines, flush-only, method-for-method ML mirror) |
| 3 | #61 | `57ddf67` | `DlService` atomic flow (~+841 lines incl. ThreadSafeLRU metrics cache) |
| 4 | #62 | `8994fd5` | CLI + API surfaces (~+966 lines incl. regenerated `API_SPECIFICATION.md`) |
| 5 | #63 | `68d4640` | Citation sweep (stale D-A7 → correct D-A1/D-A8 references) |

Branch `main` at `68d4640`; GGA dual review PASSED on every slice.

### Verification (final numbers)

- Verdict: **PASS_WITH_WARNINGS**, 0 blockers, 0 CRITICAL findings; requirements 12/12, scenarios 23/23 covered by passing runtime evidence (15/15 behavior rows in the compliance matrix, zero UNTESTED scenarios).
- Fresh dl-focused runs at verification time: `tests/dl` **162 passed**, CLI/API surfaces **17 passed**; ruff check on mandated paths exit 0.
- Full-suite sweep at slice 5 (recorded evidence): **1495 passed / 0 failed / 1 skipped (807s)**.
- Strict TDD: active throughout (`tdd: true`); 69 change-local tests across RED-first slices.

### Real-data smoke (production-shape proof)

`lip dl train --lottery baloto`: snapshot id=1 created ACTIVE, cut=305, window=10, 2 weight blobs (30,793 B mlp / 211,998 B lstm), 10 Decimal metric rows. Rerun idempotent: same fingerprint/checksum, zero writes.

### Review ledger

Native runtime complete: lifetime 7,930 reviewed lines across gen3 attempts; two mechanical budget resets documented. No open review debt.

## Task Completion Gate

Persisted artifact audited directly (`openspec/changes/dl-snapshot-persistence/tasks.md`):

- Counted at archive time: **22 checked `[x]` / 0 unchecked `[ ]`** (exact `grep -c` count; no indented or alternate-format checkboxes exist). Phases 1–6 fully checked.
- **Count discrepancy recorded, not silently resolved**: the launch prompt states "All 24 tasks [x]" and `verify-report.md` §2 is titled "24/24"; the persisted artifact contains exactly 22 checkbox rows. All three sources agree on the material fact (zero unchecked implementation tasks), so the gate PASSES; the authoritative completion count per the rank-2 persisted artifact is **22/22**. No reconciliation edit was made — checkboxes were already fully marked.

## Spec Sync — NONE REQUIRED (zero-delta change)

No delta application was performed, deliberately:

1. Both delta specs under the change dir (`specs/dl-engine/spec.md`, `specs/backend/spec.md`) are **coverage maps only** — independent inspection found zero `## ADDED/MODIFIED/REMOVED/RENAMED Requirements` sections in either file; both declare "No Requirement Deltas".
2. Normative text already lives in the main specs: `openspec/specs/dl-engine/spec.md` (DLE-01..16 + DE-01/02) and `openspec/specs/backend/spec.md` (REQ-10 dl paragraph, REQ-11 dl paragraph + route-limit scenario, REQ-12 CLI paragraph) — line citations verified in `verify-report.md` §3 at verification time.
3. This change implements existing requirements verbatim; there was nothing to merge into `openspec/specs/`, and inventing a merge would corrupt the audit trail.
4. Config `rules.archive: warn before merging destructive deltas` — trivially satisfied: nothing was merged, nothing destructive occurred.

## Mechanical Copy Contract

No copy or move operations were executed in this phase (zero-delta sync + orchestrator-directed in-place closure). Consequently no `diff -r` readback applies — its absence here is BY DESIGN, not a skipped verification. No existing artifact bytes were routed through model Read→Write; the only file produced is this additive report.

## Gates

| Gate | Outcome |
|------|---------|
| Native Review Receipt Gate | `reviewGate` structurally absent from launch status — no receipt-driven gate blocks this candidate; GGA dual review PASSED on every slice per final-state facts. Archive proceeded under ordinary repository policy. |
| CRITICAL block | None — verdict PASS_WITH_WARNINGS, `critical_findings: 0`. |
| Task Completion Gate | PASSED — 22/22 `[x]`, 0 unchecked in persisted artifact. |
| Action Context Guard | No `workspace-planning` mode, no `allowedEditRoots` restriction reported; edits confined to `openspec/changes/dl-snapshot-persistence/`. Git commands intentionally NOT run (orchestrator directive); all edits left in worktree (`archive-report.md` untracked, alongside the pre-existing untracked `verify-report.md`). |

## Follow-ups Routed OUT of This Change (follow-ups, NOT defects)

Recorded here per Final-State Authority so no open item is lost; none of these block closure and none were introduced as change defects:

| # | Item | Classification / suggested routing |
|---|------|------------------------------------|
| 1 | `next_version` orders String versions lexicographically (past v9 re-issues "10" → UNIQUE collision); `mark_failed` same-version collision edge in failure path below v11 generations | Cross-store fix: ML + DL stores TOGETHER (inherited verbatim from the ML mirror by design mandate). Verify-report WARNING (c). |
| 2 | Optional `SuccessEnvelope[...] \| Response` return-typing sweep on 304 paths | House-wide idiom — identical pattern at `ml.py:119` and other routers. Optional typing-debt chore. |
| 3 | Pre-existing `ruff format --check` drift in `graph/` (4 src files) + `probability/` (6 src files) | Standalone chore PR candidate; zero overlap with this change's diff proven at verification time. |
| 4 | GGA non-blocking notes from slices 1–4 | Salted-hash determinism fixture; `np.trapezoid` note; `_build_model` hyperparams smell; opt CLI placeholder objective. Backlog candidates, non-blocking. |

## Artifacts Read (traceability)

- `openspec/changes/dl-snapshot-persistence/proposal.md`
- `openspec/changes/dl-snapshot-persistence/exploration.md` (present; inventoried)
- `openspec/changes/dl-snapshot-persistence/design.md`
- `openspec/changes/dl-snapshot-persistence/tasks.md` (audited for the gate)
- `openspec/changes/dl-snapshot-persistence/specs/dl-engine/spec.md`, `specs/backend/spec.md` (delta-section scan)
- `openspec/changes/dl-snapshot-persistence/verify-report.md` (intermediate snapshot, attributed claims only)
- `openspec/config.yaml` (rules.archive), `openspec/changes/archive/*` (convention survey)
- Apply-progress referenced from verify-report §1/§6: Engram observation #1853 (`sdd/dl-snapshot-persistence/apply-progress`) — not read directly; store mode is openspec.

## Artifacts in Change Folder (final inventory)

- `proposal.md` ✅
- `exploration.md` ✅
- `design.md` ✅
- `specs/dl-engine/spec.md` ✅ · `specs/backend/spec.md` ✅ (coverage maps, zero deltas)
- `tasks.md` ✅ (22/22 tasks complete)
- `verify-report.md` ✅ (PASS_WITH_WARNINGS; kept untracked, path stable per orchestrator)
- `archive-report.md` — this file (additive)

## What Changed

- Added `openspec/changes/dl-snapshot-persistence/archive-report.md` (this file) — the sole edit of the archive phase and the closure record.

## What Did NOT Change

- No spec sync into `openspec/specs/` (zero-delta change — normative text already present).
- No folder move to `archive/`; no status-marker line added to any existing file.
- No production code, tests, or config modified; no git commands executed; nothing committed, staged, or pushed.

## Source of Truth Status

Main specs already reflect the delivered behavior and required NO update:
- `openspec/specs/dl-engine/spec.md`
- `openspec/specs/backend/spec.md`

## SDD Cycle Complete

The change has been fully planned, implemented, verified, and closed. Ready for the next change.

