# Delta — Deep Learning Frontend Page (`dl-frontend-page`)

**Change**: `dl-frontend-page` · **Store**: `openspec` · **Date**: 2026-08-23
**Artifact**: delta spec — new capability `dl-frontend-page`; ADDED requirements become the full capability spec at archive. Backend `/api/v1/dl` (`dl-engine`) is FINAL on main: this capability adds NO backend requirements and MUST NOT modify shared layers (`apiClient`, `useApi`) or any existing page.

## ADDED Requirements

### Requirement: R1: Typed DL Service Client

| Field | Value |
|-------|-------|
| **ID** | R1 |
| **RFC** | MUST |

The system SHALL provide `frontend/src/services/dl.ts` exposing `getDlModels(lotteryId): Promise<DLSnapshot>`, `getDlMetrics(lotteryId, modelId?): Promise<DLMetric[]>`, and `trainDlModels(lotteryId): Promise<DLTrainResult>` built on `apiClient`, mirroring `services/ml.ts` call shapes (`GET /dl/models?lottery_id=`, `GET /dl/metrics?lottery_id=[&model_id=]`, `POST /dl/train?lottery_id=`). `frontend/src/types/dl.ts` SHALL define `DLSnapshot {id, lottery_id, model_set, version, status, checksum, input_fingerprint, cut, window}`, `DLMetric {model_id, number, metric_name, value, params_json}`, and `DLTrainResult` with rows `{family: "mlp"\|"lstm", status, snapshot_id?, fingerprint?, metrics_checksum?, error?}` per the live API. `DLSnapshot` MUST include `window` (absent in `MLSnapshot`).

#### Scenario: typed functions call /dl/* endpoints

- GIVEN MSW handlers for `*/api/v1/dl/models`, `*/api/v1/dl/metrics`, `POST */api/v1/dl/train`
- WHEN each function executes for lottery 1
- THEN method, path, and query params match the ml.ts-mirrored shape and payloads satisfy the types above

#### Scenario: DLSnapshot carries window

- GIVEN a models payload shaped `{...,cut:305,window:10}`
- WHEN `getDlModels` resolves
- THEN the returned `DLSnapshot.window === 10`

### Requirement: R2: Snapshot Summary and Per-Model Metrics Table

| Field | Value |
|-------|-------|
| **ID** | R2 |
| **RFC** | MUST |

The `/dl` page (`pages/DL.tsx`) SHALL render the active snapshot summary showing id, version, status, checksum, input_fingerprint, cut, and window, plus a metrics `DataTable` covering rows for both `model_id` values (`mlp`, `lstm`), grouped/labeled by `model_id`. Queries SHALL be driven by `selectedLotteryId` from `useLotteryStore`; changing the selection SHALL refetch snapshot and metrics for the new lottery. No lottery selected SHALL render the standard select-lottery `EmptyState` with zero API calls and Train disabled.

#### Scenario: summary and grouped metrics render

- GIVEN a lottery is selected and MSW serves one snapshot and mlp+lstm metric rows
- WHEN the page mounts
- THEN all seven summary fields render and the table shows rows labeled `mlp` and `lstm`

#### Scenario: lottery selection drives refetch

- GIVEN lottery 1 content is rendered
- WHEN the store selection changes to lottery 2
- THEN `/dl/models` and `/dl/metrics` are requested again with `lottery_id=2`

### Requirement: R3: SNAPSHOT_NOT_FOUND Is an Empty State With Train CTA

| Field | Value |
|-------|-------|
| **ID** | R3 |
| **RFC** | MUST |

When `GET /dl/models` responds `404` with error code `SNAPSHOT_NOT_FOUND`, the page SHALL render an `EmptyState` ("no models trained yet") offering an enabled Train CTA — NOT an `ErrorState`. This mapping SHALL be implemented within new capability files only (service or page); shared layers remain untouched. Any other failure (e.g. `RESOURCE_NOT_FOUND`, 5xx) SHALL fall through to the R6 error state.

#### Scenario: not-found renders CTA, not error

- GIVEN MSW returns 404 `{error:{code:"SNAPSHOT_NOT_FOUND"}}` for `/dl/models` and empty metrics
- WHEN the page renders with a selected lottery
- THEN the EmptyState message and an enabled Train button are visible and no `role="alert"` appears

#### Scenario: unrelated 404 stays an error

- GIVEN MSW returns 404 `RESOURCE_NOT_FOUND` for `/dl/models`
- WHEN the page renders
- THEN `ErrorState` with retry renders (R6 behavior)

### Requirement: R4: Manual Train Trigger With Busy State and Result Feedback

| Field | Value |
|-------|-------|
| **ID** | R4 |
| **RFC** | MUST |

The Train button SHALL invoke `trainDlModels(selectedLotteryId)` (v1 defaults `model_set=core-3`, `window=10`, no cut/window inputs). Because the synchronous call blocks ~100s, the busy state SHALL persist for the whole request: the button SHALL be disabled with `aria-busy` set and a "Training…" label while in flight. On a successful response the page SHALL refetch snapshot and metrics. The train response MAY contain `status:"failed"` rows inside the HTTP 200 envelope; each failed row SHALL have its `error` text rendered visibly (e.g., per-family result summary). A rejected train request SHALL render `ErrorState` whose retry re-runs training (Models precedent).

#### Scenario: busy state held through slow request, refetch on success

- GIVEN the page is loaded and the POST handler delays 100ms
- WHEN Train is clicked
- THEN during the pending request the button is disabled, has `aria-busy`, reads "Training…"
- AND after the 200 response both `/dl/models` and `/dl/metrics` are called again

#### Scenario: failed family row surfaces its error text

- GIVEN POST resolves 200 with `results:[{family:"lstm",status:"failed",error:"no active F4 snapshot"}]`
- WHEN the response lands
- THEN the text "no active F4 snapshot" (or its mapped message) is visible in the results area

#### Scenario: train rejection offers retry

- GIVEN the POST handler returns 500
- WHEN Train completes
- THEN `ErrorState` renders and clicking Retry re-issues the POST

### Requirement: R5: Route and Navigation Entry

| Field | Value |
|-------|-------|
| **ID** | R5 |
| **RFC** | MUST |

`App.tsx` SHALL register `/dl` as a lazy-loaded route rendering the DL page, and `Sidebar.tsx` SHALL add a "Deep Learning" entry linking to `/dl` inside the existing ML group (dot icon convention; no new icons).

#### Scenario: deep-linking /dl works via lazy chunk

- GIVEN the application is mounted
- WHEN the router renders path `/dl`
- THEN the DL page content mounts through its lazy element

#### Scenario: sidebar exposes the page

- GIVEN the sidebar is rendered
- WHEN the ML group is inspected
- THEN it contains a link named "Deep Learning" pointing to `/dl`

### Requirement: R6: Loading and Error Parity With Models Page

| Field | Value |
|-------|-------|
| **ID** | R6 |
| **RFC** | MUST |

The page SHALL reproduce `Models.tsx` state handling: while snapshot or metrics load, a `Skeleton` placeholder renders; on fetch failure, `ErrorState` with a Retry control renders (`role="alert"`), and activating Retry refetches the failed queries and recovers to the data view when the backend succeeds.

#### Scenario: skeleton shows during fetch

- GIVEN MSW delays the models response
- WHEN the page mounts with a selected lottery
- THEN an `animate-pulse` skeleton renders until data arrives, then the table replaces it

#### Scenario: fetch failure recovers via retry

- GIVEN `/dl/models` first responds 500, then succeeds after handler override
- WHEN the page renders and the user clicks Retry
- THEN `role="alert"` shows the failure, and after retry the metrics table renders with no alert
