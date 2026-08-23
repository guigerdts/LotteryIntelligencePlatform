# Design: DL Frontend Page (`/dl`)

## Technical Approach

Mirror the ML surface 1:1 (explore obs 1860, Approach 1): new typed client `services/dl.ts` + `types/dl.ts`; single-file container page `pages/DL.tsx` cloned from `pages/Models.tsx`; lazy route `/dl` + "Deep Learning" nav entry. Zero shared-layer changes — `apiClient`/`useApi` untouched (R1–R6).

## Architecture Decisions

### D1: SNAPSHOT_NOT_FOUND → null mapping lives in `services/dl.ts`

**Choice**: (a) — `getDlModels` catches `NotFoundError`, returns `null` when `err.code === "SNAPSHOT_NOT_FOUND"`; rethrows anything else. Signature: `Promise<DLSnapshot | null>` (null = documented sentinel refining R1's happy-path shape; R3 explicitly allows "service or page").

**Alternatives**: (b) DL.tsx string-matches the error message — rejected. Evidence: `useApi.execute` stores only `err.message` (`hooks/useApi.ts:32`) — the backend `code` is unrecoverable at page level, so (b) must match human-readable copy, which breaks silently on wording changes. `NotFoundError` preserves `code` verbatim (`services/api.ts:18–23`, `throwByStatus:97`), so only the service can branch on it reliably.

**Payoff**: useApi resolves cleanly with `data:null, error:null`, so DL.tsx reuses the Models empty-state branch verbatim (`Models.tsx:107–123`: `!snapshot && rows.length === 0` → EmptyState + enabled Train CTA). Unrelated 404s/5xx rethrow → R6 ErrorState. Mapping stays inside one new file.

### D2: Types mirror `types/ml.ts` style

Row interface named `DLTrainRow` (ml.ts calls its row `MLModel`); `family` narrowed to `"mlp" | "lstm"` per R1/R4; optional fields `T | null` like `MLModel.error`. Home: `frontend/src/types/dl.ts`.

### D3: Train outcome captured in local state

Models.tsx discards the train result (`Models.tsx:87–91`). DL keeps `useState<DLTrainResult | null>` and renders failed rows' `error` text under the summary (R4). This is the only real structural deviation from the mirror.

## Component Map: copied vs adapted from Models.tsx

| Block | Source lines | Action |
|---|---|---|
| Message/button constants | 11–16 | Copy |
| `metricColumns` (model_id, number, metric_name, value) | 18–23 | Copy; pre-sort rows by `model_id` for mlp/lstm grouping (R2) |
| `SnapshotSummary` | 25–45 | Adapt: add `input_fingerprint`, `cut`, `window` spans (keeps model_set; covers R2's seven fields) |
| Three separate `useApi` instances (snapshot/metrics/train) | 54–70 | Copy verbatim |
| Loading/error aggregation, `useEffect` on `selectedLotteryId`, `refetch` | 72–85 | Copy |
| `handleTrain` guard + refetch-on-result | 87–91 | Adapt: capture result into state (D3) |
| `renderContent` ladder: no-lottery EmptyState → ErrorState(retry=refetch) → Skeleton → trainError ErrorState(retry=train) → snapshot-null CTA → DataTable | 93–139 | Copy (structurally satisfies R2/R3/R6) |
| Header Train button: `disabled={!selectedLotteryId \|\| training}`, `aria-busy={training}`, `"Training…"` label | 141–159 | Copy (busy holds entire request: isLoading true until settle) |
| `<section aria-label>` wrapper | 160–165 | Copy |
| Failed-family results list | — | New: maps `trainOutcome.results.filter(r => r.status==="failed")` to visible `${family}: ${error}` text |

## Data Flow

```
DL.tsx ─ useApi(getDlModels/getDlMetrics) ─▶ services/dl.ts ─ apiClient ─▶ GET /dl/models, /dl/metrics?lottery_id=[&model_id]
        └ useApi(trainDlModels) ──────────────────────┘                    404 SNAPSHOT_NOT_FOUND ─ catch ─▶ null
Train click ─▶ POST /dl/train (~100s sync, query-param lottery_id)
   button [disabled + aria-busy + "Training…"] held whole request
   200 {results[]} ─┬─ status:"failed" rows ─▶ trainOutcome state ─▶ visible error text
                    └─ refetch() re-issues both GETs (Models precedent, :87–91)
```

## File Changes

| File | Action | Description |
|---|---|---|
| `frontend/src/types/dl.ts` | Create | `DLSnapshot` (+`window` vs MLSnapshot), `DLMetric`, `DLTrainRow`, `DLTrainResult` |
| `frontend/src/services/dl.ts` | Create | `getDlModels`/`getDlMetrics`/`trainDlModels`; D1 mapping here |
| `frontend/src/pages/DL.tsx` | Create | Page per component map (~150 ln) |
| `frontend/src/pages/DL.test.tsx` | Create | MSW harness + 13 scenario tests (~150 ln) |
| `frontend/src/App.tsx` | Modify | +2 ln: `const DeepLearning = lazy(() => import("./pages/DL"));` after line 20; `{ path: "dl", element: <DeepLearning /> },` after line 65 (`backtesting`, before `generador`) |
| `frontend/src/components/Sidebar.tsx` | Modify | +1 ln: `{ label: "Deep Learning", to: "/dl" },` in ML group `items` after Backtesting (line 41); generic dot icon, no icon work |
| `frontend/src/App.test.tsx` | Modify | +`*/api/v1/dl/*` MSW handlers; `renderAt("/dl")` deep-link test (pattern: lines 66–69, 132–142) |
| `frontend/src/components/Sidebar.test.tsx` | Modify | +`{ label: "Deep Learning", to: "/dl" }` to `ALL_ITEMS` (lines 7–20) — existing item test asserts the href |

App.test/Sidebar.test edits are additive test coverage, not shared-layer/page changes; delta vs proposal scope noted.

## Interfaces / Contracts

```ts
export interface DLSnapshot { id: number; lottery_id: number; model_set: string;
  version: string; status: string; checksum: string; input_fingerprint: string;
  cut: number; window: number; }
export interface DLMetric { model_id: string; number: number; metric_name: string;
  value: number; params_json: string; }
export interface DLTrainRow { family: "mlp" | "lstm"; status: string;
  snapshot_id?: number | null; fingerprint?: string | null;
  metrics_checksum?: string | null; error?: string | null; }
export interface DLTrainResult { lottery_id: number; results: DLTrainRow[]; }

getDlModels(lotteryId): Promise<DLSnapshot | null>   // null ⇔ SNAPSHOT_NOT_FOUND (D1)
getDlMetrics(lotteryId, modelId?): Promise<DLMetric[]>
trainDlModels(lotteryId): Promise<DLTrainResult>     // POST, v1 defaults model_set/window server-side
```

Query shapes mirror ml.ts: `/dl/models?lottery_id=${id}`, `/dl/metrics?lottery_id=${id}${modelId ? `&model_id=${modelId}` : ""}`.

## Testing Strategy

Harness (mirror `Models.test.tsx`): `env()`/`err()` helpers, call counters, `setupServer(http.get("*/api/v1/dl/models"|metrics), http.post("*/api/v1/dl/train"))`, `selectLottery()` store setState, afterEach reset.

| Scenario | Test (DL.test.tsx unless noted) | Key assertion |
|---|---|---|
| R1-S1 typed calls hit endpoints | service describe: invoke each fn, capture request | method/path + `lottery_id=1` (+`model_id=lstm` variant) |
| R1-S2 window carried | service: resolve `{…,cut:305,window:10}` | `result.window === 10` |
| R2-S1 summary + grouped rows | mount w/ mlp+lstm fixtures | 7 summary fields; table shows `mlp` & `lstm` |
| R2-S2 selection refetch | setState lottery 2 | counters ≥2; last request `lottery_id=2` |
| R3-S1 not-found → CTA | override models → 404 `SNAPSHOT_NOT_FOUND`, metrics `[]` | EmptyState msg + enabled Train; `queryByRole("alert")` null |
| R3-S2 unrelated 404 | override → 404 `RESOURCE_NOT_FOUND` | `role="alert"` + Retry renders |
| R4-S1 busy held + refetch | POST `delay(100)` | mid-flight: disabled+`aria-busy`+"Training…"; then models/metrics called again |
| R4-S2 failed row text | POST 200 w/ lstm `status:"failed", error:"no active F4 snapshot"` | text visible in results area |
| R4-S3 rejection retry | POST 500 → ok | alert; Retry re-POSTs (`trainCalls===2`) |
| R5-S1 deep-link /dl | App.test.tsx: `renderAt("/dl")` | DL heading mounts via lazy chunk |
| R5-S2 sidebar entry | Sidebar.test.tsx (via ALL_ITEMS) | link "Deep Learning" href `/dl` |
| R6-S1 skeleton | models handler delayed | `.animate-pulse` present → replaced by table |
| R6-S2 failure recovers | models 500 → success override | alert → Retry → table, no alert |

Plus one parity bonus test: no lottery selected → zero API calls, Train disabled (R2 body).

## Threat Matrix

N/A — no shell/subprocess, VCS/PR automation, executable classification, or process-integration boundary. `/dl` is SPA client routing rendered inside the existing layout; no new trust or execution boundary introduced.

## Migration / Rollout

No migration. Fully additive: delete four new files, revert two 2-line edits (+ two test additions).

## Open Questions

- None blocking. PR-split call (single vs PR1 service+types / PR2 page) stays with sdd-tasks per proposal Delivery forecast.
