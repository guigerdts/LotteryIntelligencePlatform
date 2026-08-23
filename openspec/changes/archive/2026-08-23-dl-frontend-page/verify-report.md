```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:750a0f9d46b8cd88a2bf3f8463f3ea7347a3c90a43926fa2b497c8e4ed08d540
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 13/13
test_command: npx vitest run src/pages/DL.test.tsx src/App.test.tsx src/components/Sidebar.test.tsx
test_exit_code: 0
test_output_hash: sha256:750a0f9d46b8cd88a2bf3f8463f3ea7347a3c90a43926fa2b497c8e4ed08d540
build_command: npx tsc -b --force
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# Verification Report — dl-frontend-page

**Change**: `dl-frontend-page` · **Mode**: openspec · **Evidence revision**: main @ `9d97b93` (PR #64, 12 files, +997; tree clean at verify time)
**Strict TDD**: inactive (no cached capabilities/config in `.atl/`; runner vitest) → **Standard verification** · **Verdict**: **PASS WITH WARNINGS**

## 1. Artifact completeness

| Artifact | Present | Used |
|---|---|---|
| proposal.md | ✅ | ✅ |
| design.md | ✅ | ✅ |
| tasks.md | ✅ | ✅ |
| specs/dl-frontend-page/spec.md (delta, all-ADDED capability) | ✅ | ✅ |
| PR #64 / commit `9d97b93` diffstat + orchestrator post-merge smoke record | ✅ | ✅ |

## 2. Task completeness — 24/25 `[x]`, one evidence-backed residual

Phases 1–3 fully checked (types/service → page → route/nav). Phase 4: 4.1 and 4.2 checked; **4.3 unchecked in tasks.md but substantively executed post-merge per orchestrator final-state facts**: dev servers lifted (`uvicorn :8000`, `vite :5173`), `curl localhost:5173/api/v1/dl/models?lottery_id=1` returned a live DL snapshot through the vite proxy, and `GET /dl` served the SPA shell (title verified). Residuals routed in §6 (checkbox staleness + owner-owned visual confirmation; optional ~100 s real train intentionally skipped — idempotent fingerprint short-circuit already proven in `dl-snapshot-persistence`). Not treated as CRITICAL: every automatable scenario has fresh runtime proof (§4), and the remaining items are explicitly optional/owner-owned.

Merge-time recorded evidence (not re-run per orchestrator instruction): full vitest **150 passed / 22 files (~12 min)**; eslint clean on touched files; GGA PASSED; CI frontend shard green.

## 3. Zero shared-layer delta — CONFIRMED

PR diffstat touches only new capability files (`types/dl.ts`, `services/dl.ts`, `pages/DL.tsx`, `pages/DL.test.tsx`) plus additive edits (`App.tsx` +2, `Sidebar.tsx` +1, their tests) and the four openspec artifacts. `apiClient`/`parseResponse`/`throwByStatus` (`services/api.ts`) and `hooks/useApi.ts` are untouched; no existing page modified — spec header constraint honored.

## 4. Spec compliance matrix (requirement → scenario → code → passing test)

Runtime proof this session (fresh runs from `frontend/`): focused suite **26/26 passed, 3 files, exit 0** (DL 12 + App 6 + Sidebar 8); `npx tsc -b --force` **exit 0**, zero output.

| Req | Scenario | Implementation | Covering test (passed at runtime) | Result |
|---|---|---|---|---|
| R1 | typed functions call /dl/* endpoints | `services/dl.ts:5-33`; `types/dl.ts:2-37` | `DL.test.tsx > DL service client > calls the /dl/* endpoints with ml.ts-mirrored shapes (R1-S1)` — method/path/query incl. `model_id=lstm` variant | ✅ COMPLIANT |
| R1 | DLSnapshot carries window | `types/dl.ts:11` (`window: number`) | `…carries window through DLSnapshot (R1-S2)` — `window===10`, `cut===305` | ✅ COMPLIANT |
| R2 | summary + grouped metrics render | `DL.tsx:28-62` (SnapshotSummary: id/model_set/version/status/checksum/input_fingerprint/cut/window), `:26,:111-113` (FAMILY_ORDER pre-sort) | `…renders the snapshot summary fields and model_id-grouped metric rows (R2-S1)` — all 8 spans asserted; table text index of `mlp` < `lstm` | ✅ COMPLIANT |
| R2 | lottery selection drives refetch | `DL.tsx:90-94` (`useEffect` on `selectedLotteryId`) | `…refetches snapshot and metrics when the lottery selection changes (R2-S2)` — counters ≥2, last URLs carry `lottery_id=2` | ✅ COMPLIANT |
| R2 | no-lottery body (zero calls, Train disabled) | `DL.tsx:116-118,:184` | parity bonus test — `modelsCalls/metricsCalls/trainCalls === 0`, button disabled | ✅ COMPLIANT |
| R3 | not-found renders CTA, not error | D1 mapping `services/dl.ts:16-25` → `null`; CTA branch `DL.tsx:128-144` | `…renders the empty-state Train CTA on 404 SNAPSHOT_NOT_FOUND, not an error (R3-S1)` — message visible, Train enabled, `queryByRole("alert")` null | ✅ COMPLIANT |
| R3 | unrelated 404 stays an error | rethrow at `services/dl.ts:23`; ErrorState `DL.tsx:119-121` | `…keeps an unrelated 404 as an error with retry (R3-S2)` — `role="alert"` + Retry present | ✅ COMPLIANT |
| R4 | busy held through slow request, refetch on success | header button `DL.tsx:181-189` (`disabled={!selectedLotteryId \|\| training}`, `aria-busy={training}`, `"Training…"`); refetch `:102-109` | `…holds the busy state through a slow train and refetches on success (R4-S1)` — mid-flight disabled+aria-busy+"Training…" under `delay(100)`; models/metrics each +1 after settle | ✅ COMPLIANT |
| R4 | failed family row surfaces its error text | outcome state `DL.tsx:85,:105-108`; failed-row block `:158-166` | `…surfaces a failed family row's error text from a 200 train response (R4-S2)` — "lstm: no active F4 snapshot" visible | ✅ COMPLIANT |
| R4 | train rejection offers retry | trainError ErrorState retry=`handleTrain` `DL.tsx:125-127` | `…renders an ErrorState when training rejects and Retry re-issues the POST (R4-S3)` — alert shown; `trainCalls` 1→2 | ✅ COMPLIANT |
| R5 | deep-linking /dl via lazy chunk | lazy import `App.tsx:21`; route `{ path: "dl" }` `App.tsx:67` (after `backtesting`, before `generador`) | `App.test.tsx > deep-links to the Deep Learning page at /dl through its lazy chunk` — heading + "Deep learning results" region mount | ✅ COMPLIANT |
| R5 | sidebar exposes the page | `Sidebar.tsx:42` `{ label: "Deep Learning", to: "/dl" }` in ML group after Backtesting, dot-icon convention | `Sidebar.test.tsx > renders every navigation item with its route` — ALL_ITEMS entry asserts href `/dl` | ✅ COMPLIANT |
| R6 | skeleton shows during fetch | `DL.tsx:122-124` `<Skeleton variant="card" />` | `…shows the skeleton while models load, then the table replaces it (R6-S1)` — `.animate-pulse` present → null after table | ✅ COMPLIANT |
| R6 | fetch failure recovers via retry | `DL.tsx:119-121` ErrorState retry=`refetch` | `…recovers to the data view after a failed fetch is retried (R6-S2)` — alert → Retry → table, no alert | ✅ COMPLIANT |

**Compliance summary**: 13/13 scenarios compliant (+1 R2-body bonus case). Zero UNTESTED, zero FAILING, zero PARTIAL.

## 5. Correctness (static evidence)

| Requirement | Status | Notes |
|---|---|---|
| R1 Typed DL Service Client | ✅ Implemented | Three functions mirror `ml.ts` shapes exactly (`/dl/models?lottery_id=`, `/dl/metrics?lottery_id=[&model_id=]`, `POST /dl/train?lottery_id=`); types match live API incl. required `window` on `DLSnapshot` (ML fixture in `App.test.tsx:36-47` correctly lacks it) |
| R2 Summary + Metrics Table | ✅ Implemented | Seven required fields + model_set rendered; rows grouped mlp→lstm via explicit sort; store-driven queries with refetch on selection change |
| R3 SNAPSHOT_NOT_FOUND Empty State | ✅ Implemented | See §6 D1 — code-based mapping inside new capability file only |
| R4 Manual Train Trigger | ✅ Implemented | Busy semantics hold the whole request (useApi isLoading until settle); success path captures result AND refetches; failed-row text and reject-retry both wired |
| R5 Route + Navigation | ✅ Implemented | Lazy chunk + route placement per design; sidebar ML-group entry, no new icons |
| R6 Loading/Error Parity | ✅ Implemented | renderContent ladder is structurally identical to Models.tsx ordering |

## 6. Design conformance — explicit rulings

| Decision | Verdict | Evidence |
|---|---|---|
| **D1** null mapping in `services/dl.ts` via `NotFoundError.code`, no string matching | **PASS** | `services/dl.ts:20`: `error instanceof NotFoundError && error.code === "SNAPSHOT_NOT_FOUND"` → `return null`, else rethrow (`:23`). Branches on the typed envelope code preserved verbatim by `api.ts:18-23` + `throwByStatus:97` — zero human-readable-copy matching anywhere. Signature `Promise<DLSnapshot \| null>` matches the design contract; `useApi` resolves `data:null,error:null` feeding the CTA branch |
| **D2** Types mirror `types/ml.ts` style | **PASS** | `DLTrainRow` naming, `family: "mlp" \| "lstm"` literal union, optional fields as `T \| null` (`types/dl.ts:24-31`); home paths match design File Changes table exactly |
| **D3** Train outcome captured in local state | **PASS** | `useState<DLTrainResult \| null>` `DL.tsx:85`; capture + refetch `:105-108`; failed-row rendering `:158-166` maps `${family}: ${error}` — the single sanctioned structural deviation from the Models mirror |
| Component map fidelity | **PASS** | Constants `:11-16`, metricColumns `:18-23`, three `useApi` instances `:71-83`, aggregation/effect/refetch `:87-100`, ladder order no-lottery→error→skeleton→trainError→CTA→data `:115-169`, header button `:181-189`, section wrapper `:191-196`, new failed-family list `:158-166` — all match design source-line intent |
| Query shapes | **PASS** | `/dl/models?lottery_id=`, `/dl/metrics?lottery_id=${id}${modelId ? `&model_id=${modelId}` : ""}` byte-equivalent to design Interfaces block |

## 7. Residual rulings (orchestrator items + findings)

| # | Finding | Classification | Ruling |
|---|---|---|---|
| a | Single PR #64 instead of pre-approved split (tasks forecast: chained recommended, stacked-to-main fallback) | **SUGGESTION** | Accepted deviation documented in PR body (test-file cohesion: splitting would force `DL.test.tsx` to straddle PRs). Authored diff ≈ 615 lines (997 − 382 openspec artifacts) exceeded the 400 default budget under a ratified exception. No code risk: review happened, CI green. Going forward, honor pre-approved splits or obtain explicit `size:exception` before apply |
| b | `FAMILY_ORDER` explicit sort beyond the verbatim component copy | **NO ACTION** | Sanctioned by design itself — component-map metricColumns row mandates "pre-sort rows by model_id for mlp/lstm grouping (R2)". Proven by R2-S1 ordering assertion (`indexOf("mlp") < indexOf("lstm")`) |
| c | `trainOutcome` not cleared on lottery switch — stale cross-lottery failure text persists under another lottery's data view until the next successful train | **WARNING** | Real display-correctness wart (design-silent; spec scenarios only cover post-train display, so nothing fails here). Follow-up (one line): gate the block with `trainOutcome.lottery_id === selectedLotteryId` (`DLTrainResult` already carries `lottery_id`), or reset in the selection effect. Out of this change's scope; route to a small follow-up fix |
| d | tasks.md 4.3 checkbox unchecked though smoke was executed post-merge; visual browser confirmation pending on owner; optional real train skipped | **WARNING** | Substance evidenced (curl-level proxy + SPA-shell proof recorded by orchestrator); residuals are owner-owned UX confirmation and an explicitly optional step whose risk domain (idempotent fingerprint short-circuit) was proven in `dl-snapshot-persistence`. Action: tick 4.3 with the smoke record attached once owner confirms visuals — keep the artifact truthful before archive |
| e | tasks.md 4.1 claims "14 DL cases"; actual file holds 12 DL-local tests (13 change-new counting App deep-link) | **SUGGESTION** | Bookkeeping imprecision only; coverage itself is complete (13/13 scenarios). Correct the count when ticking 4.3 |
| f | React `act(...)` console warnings during vitest (spanning pre-existing App tests and new DL tests alike) | **SUGGESTION** | Suite-wide pattern, non-blocking (all green), not introduced by this change. Candidate standalone chore: act-wrap state updates or set `IS_REACT_ACT_ENVIRONMENT` consistently |

## 8. Issues summary

- **CRITICAL**: none.
- **WARNING**: 2 — item (c) stale `trainOutcome` across lottery switches (one-line follow-up); item (d) task 4.3 checkbox staleness + owner-pending visual confirmation.
- **SUGGESTION**: 3 — item (a) single-PR process deviation (accepted, documented); item (e) task-count bookkeeping; item (f) act() warning chore.

## 9. Command evidence (this verification)

| Command (cwd `frontend/`) | Exit | Output sha256 |
|---|---|---|
| `npx vitest run src/pages/DL.test.tsx src/App.test.tsx src/components/Sidebar.test.tsx` | 0 | `750a0f9d46b8cd88a2bf3f8463f3ea7347a3c90a43926fa2b497c8e4ed08d540` |
| `npx tsc -b --force` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty output) |

Full-suite re-run intentionally skipped per orchestrator instruction; merge-time record cited in §2 (150 passed / 22 files, ~12 min).

**Final verdict: PASS WITH WARNINGS** — implementation conforms to proposal/design/tasks with 13/13 scenarios freshly proven; two warnings routed: a one-line stale-outcome UI follow-up and the 4.3 artifact-truthfulness closure (owner visual pass).
