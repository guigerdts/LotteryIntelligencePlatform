# Tasks: DL Frontend Page (`/dl`)

Order: types → service → page → route/nav. TDD: RED test task before each code task. Run commands from `frontend/`. Threat matrix: N/A (design). Includes design-delta scope the proposal missed: additive `App.test.tsx`/`Sidebar.test.tsx` edits (~15 ln).

## Phase 1: Types & Service Client

- [x] 1.1 Create `src/types/dl.ts`: `DLSnapshot` (adds `window` vs `MLSnapshot`), `DLMetric`, `DLTrainRow` (`family:"mlp"|"lstm"`), `DLTrainResult` (D2). Done: `npm run build` (tsc -b) passes.
- [x] 1.2 RED `src/pages/DL.test.tsx`: MSW harness (`env`/`err` helpers, `setupServer` for `*/api/v1/dl/models|metrics|train`, `selectLottery()`, afterEach reset) + service tests — R1-S1 method/path/query incl `lottery_id=1` and `model_id=lstm` variant; R1-S2 `{cut:305,window:10}` → `window===10`. Done: `npm run test -- DL` red (modules absent).
- [x] 1.3 GREEN `src/services/dl.ts`: `getDlModels`/`getDlMetrics`/`trainDlModels` mirroring `ml.ts` shapes; D1 mapping here — catch `NotFoundError` code `SNAPSHOT_NOT_FOUND` → return `null`, else rethrow. Done: `npm run test -- DL` service block green.

Commit WU1: `feat(dl-ui): add dl types and service client with not-found mapping`

## Phase 2: Page

- [x] 2.1 RED add R2 tests: S1 seven summary fields + `mlp`/`lstm` labeled rows; S2 selection change → refetch with `lottery_id=2`; bonus: no lottery → zero API calls, Train disabled. Done: `npm run test -- DL` red (page absent).
- [x] 2.2 GREEN create `src/pages/DL.tsx` per component map: clone `Models.tsx`; `SnapshotSummary` + `input_fingerprint`/`cut`/`window`; metric rows pre-sorted by `model_id`; three `useApi` instances; `renderContent` ladder; Train button `disabled={!selectedLotteryId || training}` + `aria-busy` + `"Training…"`. Done: R2 cases green.
- [x] 2.3 RED add R3 tests (S1 404 `SNAPSHOT_NOT_FOUND` → EmptyState + enabled Train, `queryByRole("alert")` null; S2 404 `RESOURCE_NOT_FOUND` → alert + Retry) and R6 tests (S1 delayed models → `.animate-pulse` then table; S2 500 → success override → Retry recovers, alert clears). Done: those cases red.
- [x] 2.4 GREEN close gaps in `DL.tsx`: null-snapshot CTA branch consuming D1 `null`; `ErrorState` retry=`refetch`; skeleton parity. Done: `npm run test -- DL` green.
- [x] 2.5 RED add R4 tests: S1 POST `delay(100)` → mid-flight disabled + `aria-busy` + `"Training…"`, then `/dl/models`+`/dl/metrics` recalled; S2 200 envelope with lstm `status:"failed"`, `error:"no active F4 snapshot"` visible; S3 POST 500 → alert, Retry re-POSTs (`trainCalls===2`). Done: red.
- [x] 2.6 GREEN extend `handleTrain` (D3): capture `DLTrainResult` into local state; render `${family}: ${error}` for failed rows; train-failure `ErrorState` whose retry reruns training; full refetch on success. Done: `npm run test -- DL` green.

Commit WU2: `feat(dl-ui): add /dl page with models-parity states and train feedback`

## Phase 3: Route & Navigation

- [x] 3.1 RED `src/App.test.tsx`: add `*/api/v1/dl/*` handlers + `renderAt("/dl")` deep-link test asserting DL mounts via lazy chunk (R5-S1). Done: red (no route yet).
- [x] 3.2 GREEN `src/App.tsx`: lazy `DeepLearning` import + `{ path: "dl", element: <DeepLearning /> }` after `backtesting`, before `generador`. Done: App tests green.
- [x] 3.3 RED `src/components/Sidebar.test.tsx`: append `{ label: "Deep Learning", to: "/dl" }` to `ALL_ITEMS` (R5-S2). Done: item test red.
- [x] 3.4 GREEN `src/components/Sidebar.tsx`: ML-group entry after Backtesting, dot-icon convention, no new icons. Done: `npm run test -- Sidebar App DL` green.

Commit WU3: `feat(dl-ui): register /dl route and sidebar deep-learning entry`

## Phase 4: Verification

- [x] 4.1 `npm run test` — full suite green. [Archive-time count correction per verify-report §7(e): DL-local file holds 12 cases (13 change-new counting the App deep-link); merge-time record: 150 passed / 22 files.]
- [x] 4.2 `npm run lint && npm run build` — eslint + tsc/vite clean.
- [x] 4.3 Smoke on dev servers: `/dl` renders via sidebar link, selection refetches; optional real train (~100 s) completes and refreshes lists. [Archive-time tick per orchestrator final-state facts (verify-report §7d): post-merge smoke executed — uvicorn :8000 + vite :5173 lifted, `curl localhost:5173/api/v1/dl/models?lottery_id=1` returned live DL JSON through the vite proxy, `GET /dl` served the SPA shell. Owner visual confirmation pending as explicit note; optional ~100 s real train intentionally skipped — idempotent fingerprint short-circuit already proven in dl-snapshot-persistence.]

## Review Workload Forecast

Design file list totals **~350–465 authored changed lines**: types ~30, service ~35, DL.tsx ~150, DL.test.tsx ~120–150, App.tsx/Sidebar.tsx +3, App.test.tsx/Sidebar.test.tsx ~+15. Range straddles the 400-line budget (upper bound 465) → Medium risk. Work-unit commits WU1–WU3 stay reviewable alone; if the final diff exceeds 400, execute the pre-approved fallback split without reopening the decision: PR1 = WU1 service+types+their tests (~70 ln), PR2 = WU2+WU3 page+route+nav+tests (~330 ln), stacked to main.

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | dl types + service + R1 tests | PR1 (if split) | `npm run test -- DL` (service block) | N/A — pure client fns proven by MSW unit tests | Delete `src/types/dl.ts`, `src/services/dl.ts`; no other file touched |
| 2 | DL page + component tests | PR2 (if split) | `npm run test -- DL` | N/A — jsdom+MSW proves all render states | Delete `src/pages/DL.tsx`, `src/pages/DL.test.tsx` |
| 3 | route + nav + additive test edits | PR2 (if split) | `npm run test -- App Sidebar` | N/A — routing/nav asserted in vitest | Revert 2-line + 1-line edits and test additions |
