# Frontend Dashboard Specification — Fase 14

## Purpose

Defines the React SPA dashboard that composes all existing backend v1 API modules into interactive views. Zero backend modifications; frontend consumes real endpoints only.

## Non-Goals

| Item | Reason |
|------|--------|
| Backend `/dashboard/*` endpoints | Aspirational (API_SPEC §13), deferred indefinitely |
| Backend `/generator/*` endpoints | Generator uses `/gen/*` exclusively |
| Backend Tendencias / IA | No engine exists |
| Auth / JWT | v1 has none |
| SSR / Next.js | SPA is sufficient; Next.js adds unnecessary complexity |
| Production deploy / Docker / nginx | Out of scope |
| Fase 15–17 | Separate roadmap items |

---

## Requirements

### R1: Frontend Scaffold

| Field | Value |
|-------|-------|
| **ID** | R1 |
| **RFC** | MUST |

The system SHALL provide a React 19 + Vite + Tailwind CSS project under `frontend/` with: `package.json`, `vite.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `index.html`, `postcss.config.js`. Scripts `dev`, `build`, `lint`, `test` SHALL be present. The directory structure SHALL follow `src/{pages,layouts,components,charts,hooks,services,store,types}`.

**Scenario: Scaffold starts**

- GIVEN a fresh clone
- WHEN `npm install && npm run dev` executes
- THEN Vite serves on `localhost:5173` without errors
- AND the dev server is reachable by the backend CORS config (`allowed_origins: ["http://localhost:5173"]`)

**Scenario: Build succeeds**

- GIVEN the scaffolded project
- WHEN `npm run build` executes
- THEN a `dist/` directory is produced with zero errors

---

### R2: Routing

| Field | Value |
|-------|-------|
| **ID** | R2 |
| **RFC** | MUST |

The system SHALL use `react-router-dom` (v7) with `createBrowserRouter`. Routes SHALL map 1:1 to page components: `/` (Inicio), `/historial`, `/estadisticas`, `/heatmaps`, `/tendencias`, `/redes`, `/monte-carlo`, `/ia`, `/modelos`, `/experimentos`, `/backtesting`, `/generador`. All routes SHALL render inside `DashboardLayout`. Lazy loading via `React.lazy` + `Suspense` SHALL be applied per route.

**Scenario: Navigation to each route**

- GIVEN the SPA is loaded
- WHEN the user navigates to `/estadisticas`
- THEN the Statistics page renders inside the dashboard layout
- AND no full-page reload occurs

**Scenario: Unknown route**

- GIVEN the SPA is loaded
- WHEN the user navigates to `/unknown`
- THEN a 404-style fallback renders (not a blank screen)

---

### R3: Layout & Navigation

| Field | Value |
|-------|-------|
| **ID** | R3 |
| **RFC** | MUST |

The system SHALL render a persistent sidebar (left), a top header bar, and a scrollable main content area. Sidebar items SHALL be grouped into categories:

| Category | Items |
|----------|-------|
| General | Inicio (`/`), Historial (`/historial`) |
| Análisis | Estadísticas (`/estadisticas`), Heatmaps (`/heatmaps`), Tendencias (`/tendencias`) |
| Avanzado | Monte Carlo (`/monte-carlo`), Redes (`/redes`), IA (`/ia`) |
| ML | Modelos (`/modelos`), Experimentos (`/experimentos`), Backtesting (`/backtesting`) |
| Generador | Generador (`/generador`) |

Sidebar SHALL collapse to icons on `< md` breakpoints. Active route SHALL be visually highlighted. Stub pages (Tendencias, IA) SHALL appear in navigation.

**Scenario: Sidebar groups render**

- GIVEN the dashboard layout mounts
- WHEN the sidebar renders
- THEN navigation items are grouped under the five categories
- AND each item has a visible label and icon

**Scenario: Mobile collapse**

- GIVEN a viewport width < 768px
- WHEN the dashboard loads
- THEN the sidebar collapses to an icon-only strip
- AND a hamburger toggle re-expands it

---

### R4: Global Lottery Selector

| Field | Value |
|-------|-------|
| **ID** | R4 |
| **RFC** | MUST |

The system SHALL provide a global lottery selector in the header. The selector SHALL be backed by a Zustand store with `persist` middleware (localStorage key `lip:selectedLottery`). The selector SHALL call `GET /api/v1/lotteries` on mount to populate options. Modules that consume `lottery_id` or `lottery_code` (Historial, Estadísticas, Heatmaps, Redes, Monte Carlo, Modelos, Experimentos, Backtesting, Generador) SHALL read from this global store. Modules that do NOT use lottery filtering (Inicio, Tendencias, IA) SHALL NOT be affected by the selector.

**Scenario: Selector persists across navigation**

- GIVEN the user selects lottery "L1"
- WHEN the user navigates to Estadísticas and back to Historial
- THEN lottery "L1" remains selected

**Scenario: Selector persists across sessions**

- GIVEN the user selects lottery "L2"
- WHEN the browser session ends and a new session starts
- THEN lottery "L2" is restored from localStorage

**Scenario: No duplicate selectors**

- GIVEN the global selector is present in the header
- WHEN any module renders
- THEN no module renders its own lottery selector unless technically required (e.g., Generator needs `lottery_id` for its POST body, but the value comes from the global store)

---

### R5: API Service Layer

| Field | Value |
|-------|-------|
| **ID** | R5 |
| **RFC** | MUST |

The system SHALL provide a service layer under `src/services/` with one file per domain: `api.ts`, `lotteries.ts`, `draws.ts`, `statistics.ts`, `probability.ts`, `graph.ts`, `ml.ts`, `experiments.ts`, `backtesting.ts`, `gen.ts`. The base HTTP client in `api.ts` SHALL:
- Read `VITE_API_BASE_URL` from env, defaulting to `/api/v1`
- Parse the `SuccessEnvelope {success, data, timestamp}` and `ErrorEnvelope {success, error: {code, message}, timestamp}`
- Map HTTP status codes to typed errors: 404 → `NotFoundError`, 409 → `ConflictError`, 422 → `ValidationError`, 500+ → `ServerError`
- Expose typed request/response interfaces matching backend Pydantic schemas

**Scenario: Successful envelope parsing**

- GIVEN the backend returns `{success: true, data: {...}, timestamp: "..."}`
- WHEN the service calls a GET endpoint
- THEN the unwrapped `data` object is returned

**Scenario: Error envelope handling**

- GIVEN the backend returns `{success: false, error: {code: "GEN_NO_SELECTION", message: "..."}, timestamp: "..."}`
- WHEN the service calls an endpoint
- THEN the error is thrown with code and message accessible

---

### R6: Types

| Field | Value |
|-------|-------|
| **ID** | R6 |
| **RFC** | SHALL |

The system SHALL provide TypeScript interfaces in `src/types/` mirroring backend Pydantic schemas: `LotteryRead`, `DrawRead`, `DrawNumberRead`, `FrequencyRow`, `FrequencyList`, `GapRow`, `GapList`, `AverageRow`, `AverageList`, `GenerationResult`, `CombinationRow`, `CombinationList`, `SnapshotResult`, `SnapshotList`, `ProbabilityList`, `ProbRow`, `GraphValuesResponse`, `ComputeSnapshot`, `BtRunResponse`, `BtResultResponse`, `BtHistoryEntry`, `ExperimentResponse`, `ComparisonResponse`, `Envelope<T>`, `ErrorEnvelope`.

---

### R7: Inicio (Home)

| Field | Value |
|-------|-------|
| **ID** | R7 |
| **RFC** | MUST |

The Inicio page SHALL be a landing/operational summary. It SHALL display:
1. **Latest draws**: last 5 draws from `GET /api/v1/draws?order=desc&page_size=5` (filtered by global lottery)
2. **Statistics summary**: frequency snapshot from `GET /api/v1/statistics/{code}/frequencies` for the global lottery — top-5 most/least frequent numbers
3. **System health**: `GET /api/v1/health` and `GET /api/v1/version` as a secondary info block (not the main content)

Loading state SHALL show skeleton placeholders. Empty state SHALL show "No data available for this lottery." Error state SHALL show a retry button.

**Scenario: Home loads with data**

- GIVEN the global lottery is set
- WHEN the Home page mounts
- THEN latest draws, statistics summary, and system health render
- AND the statistics summary shows top-5 most/least frequent numbers

**Scenario: Home with no draws**

- GIVEN the global lottery has zero draws
- WHEN the Home page mounts
- THEN an empty state message renders
- AND no error is thrown

---

### R8: Historial

| Field | Value |
|-------|-------|
| **ID** | R8 |
- **RFC** | MUST |

The Historial page SHALL list draws from `GET /api/v1/draws?lottery={code}&order=desc&page_size=50`. Clicking a draw SHALL show detail via `GET /api/v1/draws/{id}`. The lottery filter SHALL use the global lottery selection. Pagination SHALL use `page` query param. Draw detail SHALL show draw number, date, numbers, super number, jackpot, winners.

**Scenario: Draw list renders**

- GIVEN the global lottery is "L1"
- WHEN the Historial page mounts
- THEN draws for "L1" are listed in descending order

**Scenario: Draw detail view**

- GIVEN the draw list is rendered
- WHEN the user clicks a draw row
- THEN the detail panel shows all draw fields

---

### R9: Estadísticas

| Field | Value |
|-------|-------|
| **ID** | R9 |
| **RFC** | MUST |

The Estadísticas page SHALL display three chart views for the global lottery: Frequencies (`GET /api/v1/statistics/{code}/frequencies`), Gaps (`GET /api/v1/statistics/{code}/gaps`), Averages (`GET /api/v1/statistics/{code}/averages`). Charts SHALL use Recharts. A "Generate Snapshot" button SHALL call `POST /api/v1/statistics/generate` with `lottery_code` from the global store.

| Chart Type | Data Source | Visualization |
|------------|-------------|---------------|
| Frequencies | `frequencies[].{number, count}` | Bar chart (x: number, y: count) |
| Gaps | `gaps[].{number, min_gap, max_gap, avg_gap}` | Line chart (x: number, y: avg_gap, range: min-max) |
| Averages | `averages[series_key].{mean, non_null_count}` | Bar chart per series |

**Scenario: Frequencies chart renders**

- GIVEN the global lottery has a statistics snapshot
- WHEN the Estadísticas page mounts
- THEN a bar chart shows frequency distribution

**Scenario: Generate snapshot**

- GIVEN no active statistics snapshot exists
- WHEN the user clicks "Generate Snapshot"
- THEN `POST /api/v1/statistics/generate` is called
- AND a loading indicator shows until completion
- AND charts render with the new data

---

### R10: Heatmaps

| Field | Value |
|-------|-------|
| **ID** | R10 |
| **RFC** | MUST |

The Heatmaps page SHALL visualize cooccurrence data from `POST /api/v1/graph/compute` (trigger) and `GET /api/v1/graph/{code}/snapshots?graph_type=cooccurrence` (list), then `GET /api/v1/graph/{code}/snapshots/{id}` (values). Visualization SHALL use Recharts heatmap or custom SVG grid. The user SHALL be able to trigger computation and select a snapshot.

**Scenario: Compute cooccurrence**

- GIVEN the global lottery is selected
- WHEN the user clicks "Compute"
- THEN `POST /api/v1/graph/compute` is called with `graph_type: "cooccurrence"`
- AND the snapshot list refreshes

---

### R11: Redes (Network Graph)

| Field | Value |
|-------|-------|
| **ID** | R11 |
| **RFC** | MUST |

The Redes page SHALL render an interactive force-directed graph using `react-force-graph-2d` (lazy-loaded). Data SHALL come from `GET /api/v1/graph/{code}/snapshots?graph_type=network` and `GET /api/v1/graph/{code}/snapshots/{id}`. Nodes SHALL be lottery numbers; links SHALL represent cooccurrence strength (edge weight).

**Scenario: Network graph renders**

- GIVEN a network graph snapshot exists for the global lottery
- WHEN the Redes page mounts
- THEN nodes and links render in an interactive force-directed layout

**Scenario: Lazy load**

- GIVEN the user navigates to Redes
- WHEN the route mounts
- THEN `react-force-graph-2d` is loaded dynamically (not in the main bundle)

---

### R12: Tendencias (Stub)

| Field | Value |
|-------|-------|
| **ID** | R12 |
| **RFC** | MUST |

The Tendencias page SHALL render an empty-state UI with message "Próximamente — Análisis de tendencias disponible en una futura fase." It SHALL NOT call any backend endpoint. It SHALL be visible in the sidebar under Análisis.

**Scenario: Tendencias empty state**

- GIVEN the user navigates to `/tendencias`
- WHEN the page renders
- THEN an empty-state message is displayed
- AND no API calls are made

---

### R13: Monte Carlo

| Field | Value |
|-------|-------|
| **ID** | R13 |
| **RFC** | MUST |

The Monte Carlo page SHALL call `POST /api/v1/probability/generate` (trigger) and `GET /api/v1/probability/{code}/probabilities` (read) for the global lottery. It SHALL display a form to trigger generation and a table/list of probability rows (`ProbRow`: model_id, subject, draw_number, value).

**Scenario: Generate probabilities**

- GIVEN the global lottery is selected
- WHEN the user clicks "Generate"
- THEN `POST /api/v1/probability/generate` is called
- AND a loading state shows until completion
- AND probability rows render in a table

---

### R14: IA (Stub)

| Field | Value |
|-------|-------|
| **ID** | R14 |
| **RFC** | MUST |

The IA page SHALL render an empty-state UI with message "Fase 15 — AI Assistant." It SHALL NOT call any backend endpoint. It SHALL be visible in the sidebar under Avanzado.

**Scenario: IA empty state**

- GIVEN the user navigates to `/ia`
- WHEN the page renders
- THEN an empty-state message is displayed
- AND no API calls are made

---

### R15: Modelos

| Field | Value |
|-------|-------|
| **ID** | R15 |
| **RFC** | MUST |

The Modelos page SHALL call `GET /api/v1/ml/models?lottery_id={id}` and `GET /api/v1/ml/metrics?lottery_id={id}`. It SHALL display a list of active model families and their metrics. A "Train" button SHALL call `POST /api/v1/ml/train?lottery_id={id}`.

**Scenario: Models list renders**

- GIVEN an active ML snapshot exists
- WHEN the Modelos page mounts
- THEN model families and their status render

---

### R16: Experimentos

| Field | Value |
|-------|-------|
| **ID** | R16 |
| **RFC** | MUST |

The Experimentos page SHALL support: list (`GET /api/v1/experiment/?lottery_id={id}`), create (`POST /api/v1/experiment/create`), detail (`GET /api/v1/experiment/{id}`), run (`POST /api/v1/experiment/{id}/run`), compare (`POST /api/v1/experiment/{id}/compare`). All operations SHALL use the global lottery ID.

**Scenario: Create and list experiments**

- GIVEN the global lottery is selected
- WHEN the user creates an experiment with name "Test"
- THEN `POST /api/v1/experiment/create` is called
- AND the experiment appears in the list

---

### R17: Backtesting

| Field | Value |
|-------|-------|
| **ID** | R17 |
| **RFC** | MUST |

The Backtesting page SHALL support: run (`POST /api/v1/backtesting/run`), history (`GET /api/v1/backtesting/history?lottery_id={id}`), results (`GET /api/v1/backtesting/results?lottery_id={id}`). A form SHALL collect `strategy_id`, `train_years`, `eval_count`, `step_count`, `min_train_draws`, `seed`. Results SHALL display aggregate metrics (hit_rate, average_matches, consistency_score, total_draws_evaluated).

**Scenario: Run backtest**

- GIVEN the global lottery is selected and form fields are filled
- WHEN the user clicks "Run Backtest"
- THEN `POST /api/v1/backtesting/run` is called with the form data
- AND a loading state shows
- AND results render on completion

---

### R18: Generador

| Field | Value |
|-------|-------|
| **ID** | R18 |
| **RFC** | MUST |

The Generador page SHALL provide inline form → execution → result on the same page (no navigation). Form fields: `lottery_id` (from global store, hidden/auto-filled), `count` (optional 1–100, default 10), `seed` (optional), `selection_id` (optional). Execution calls `POST /api/v1/gen/generate`. Result SHALL render inline showing: `combinations` (table), `snapshot_id`, `fingerprint`, `seed`, `status`. Additional actions: list snapshots (`GET /api/v1/gen/snapshots?lottery_id={id}`), read combinations of a snapshot (`GET /api/v1/gen/combinations?lottery_id={id}&snapshot_id={id}`), transition snapshot status (`POST /api/v1/gen/snapshot`).

Error codes SHALL map to user messages:

| Code | HTTP | Message |
|------|------|---------|
| `GEN_NO_SELECTION` | 404 | No active selection for this lottery |
| `GEN_NO_DISTRIBUTION` | 404 | No distribution available |
| `GEN_LOTTERY_NOT_FOUND` | 404 | Lottery not found |
| `GEN_COUNT_INVALID` | 422 | Count must be between 1 and 100 |
| `GEN_SNAPSHOT_NOT_FOUND` | 404 | Snapshot not found |
| `GEN_DUPLICATE_SNAPSHOT` | 409 | A snapshot with this fingerprint already exists |
| `GEN_SPACE_EXHAUSTED` | 422 | Generation space exhausted |

**Scenario: Generate combinations inline**

- GIVEN the global lottery is selected
- WHEN the user clicks "Generate" (count=5, seed=42)
- THEN `POST /api/v1/gen/generate` is called
- AND a spinner shows during execution
- AND combinations render in a table below the form
- AND snapshot_id, fingerprint, seed, status are displayed

**Scenario: GEN_COUNT_INVALID error**

- GIVEN the global lottery is selected
- WHEN the user enters count=0 and clicks "Generate"
- THEN `POST /api/v1/gen/generate` is called
- AND a user-friendly error "Count must be between 1 and 100" renders
- AND no navigation occurs

**Scenario: GEN_DUPLICATE_SNAPSHOT error**

- GIVEN an identical generate request was already fulfilled
- WHEN the user clicks "Generate" with the same parameters
- THEN the existing snapshot is returned (idempotent)
- AND the result shows the existing snapshot data

---

### R19: State Management (Zustand)

| Field | Value |
|-------|-------|
| **ID** | R19 |
| **RFC** | MUST |

The system SHALL use Zustand for global state. Store structure:

| Slice | Fields | Persistence |
|-------|--------|-------------|
| `useAppStore` | `selectedLotteryId`, `selectedLotteryCode`, `sidebarCollapsed` | `selectedLotteryId` + `selectedLotteryCode` via `persist` (localStorage) |
| `useModuleStore` | per-module cache (e.g., `statisticsData`, `drawsData`) | Optional, per module |

The `selectedLottery` SHALL be read by all modules that need lottery filtering. Store SHALL expose actions: `setSelectedLottery(id, code)`, `toggleSidebar()`.

---

### R20: Loading / Empty / Error States

| Field | Value |
|-------|-------|
| **ID** | R20 |
| **RFC** | MUST |

The system SHALL provide shared components: `Skeleton` (loading), `EmptyState` (no data), `ErrorState` (error with retry). Every data-fetching page SHALL use these patterns:

| State | Trigger | UI |
|-------|---------|-----|
| Loading | API call in progress | Skeleton placeholders matching layout |
| Empty | Successful response with empty data | `EmptyState` with contextual message |
| Error | API failure (4xx/5xx) | `ErrorState` with error message and retry button |

**Scenario: Loading state**

- GIVEN a page is fetching data
- WHEN the API call is in progress
- THEN skeleton placeholders render in place of content

**Scenario: Error with retry**

- GIVEN an API call fails with 500
- WHEN the error state renders
- THEN an error message and retry button are visible
- AND clicking retry re-executes the failed call

---

### R21: Error Handling

| Field | Value |
|-------|-------|
| **ID** | R21 |
| **RFC** | MUST |

The system SHALL handle HTTP errors uniformly: 404 → "Resource not found", 409 → "Conflict — resource already exists", 422 → "Validation error" + specific message, 500+ → "Server error — try again later". GEN_* error codes from the generator SHALL be mapped to user-friendly messages per R18. All errors SHALL be displayed in the module's ErrorState component (not toast/snackbar).

---

### R22: Responsive & Accessibility

| Field | Value |
|-------|-------|
| **ID** | R22 |
| **RFC** | SHALL |

The layout SHALL use Tailwind responsive classes. Breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px). Sidebar SHALL collapse on `< md`. Charts SHALL include `role="img"` and `aria-label` attributes. Form inputs SHALL have associated `<label>` elements. Focus states SHALL be visible (Tailwind `focus:ring`). Color contrast SHALL meet WCAG AA (4.5:1 for text).

---

### R23: Charts (Recharts)

| Field | Value |
|-------|-------|
| **ID** | R23 |
| **RFC** | SHALL |

Chart components SHALL live in `src/charts/`: `FrequencyChart.tsx`, `GapChart.tsx`, `AverageChart.tsx`, `DistributionChart.tsx`, `HeatmapChart.tsx`. Each chart SHALL accept typed props matching the backend response shapes. Charts SHALL be responsive (container width). Null/missing values SHALL be handled gracefully (no crashes).

---

### R24: CORS & Dev Proxy

| Field | Value |
|-------|-------|
| **ID** | R24 |
| **RFC** | SHALL |

The Vite dev server SHALL run on `localhost:5173`. The backend CORS config already allows this origin (`allowed_origins: ["http://localhost:5173"]`). No proxy configuration is required. The frontend base URL SHALL be configurable via `VITE_API_BASE_URL` env var (default: `/api/v1`).

---

### R25: Naming & Commits

| Field | Value |
|-------|-------|
| **ID** | R25 |
| **RFC** | SHALL |

The frontend project SHALL follow repo conventions: conventional commits (`feat`, `fix`, `chore`, `build`, `refactor`), no AI attribution, English code and comments, component files in PascalCase, utility/service files in camelCase.

---

## Non-Functional Requirements

| NFR | Requirement | Verifiable |
|-----|-------------|------------|
| NFR-1 | Zero backend modifications in Fase 14 | `git diff backend/` shows no changes |
| NFR-2 | No calls to nonexistent endpoints (`/dashboard/*`, `/generator/*`, Tendencias backend, IA backend) | Network tab shows no 404s to these paths |
| NFR-3 | `npm run build` produces zero errors | Build exit code 0 |
| NFR-4 | All 12 module pages render (stubs for Tendencias/IA) | Manual or automated route check |
| NFR-5 | Lottery selection persists across sessions | localStorage contains `lip:selectedLottery` |
| NFR-6 | Charts render within 2s of data load (excluding API latency) | Performance measurement |
| NFR-7 | WCAG AA color contrast on text elements | Automated audit (e.g., axe-core) |
| NFR-8 | Lazy import for react-force-graph-2d reduces initial bundle | Bundle analysis shows graph lib not in main chunk |

---

## Traceability

| Spec Section | Proposal Reference |
|--------------|--------------------|
| R1 | §4 D1 (Stack), §6 (Frontend Structure) |
| R3 | §4 (User decision: sidebar agrupado) |
| R4 | §4 (User decision: selector global) |
| R7 | §4 (User decision: Inicio as landing) |
| R12, R14 | §4 D6 (Tendencias/IA stubs) |
| R18 | §4 D7 (Generator integration) |
| R5, R6 | §3 (API service layer) |
| R19 | §4 D4 (Zustand) |
| R20-R22 | §11 (Success Criteria: responsive) |
| Non-Goals | §2 (Out of Scope) |
