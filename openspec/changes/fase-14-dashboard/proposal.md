# Proposal: Fase 14 — Dashboard

## 1. Intent

The backend exposes 12+ API modules (lotteries, draws, statistics, probability, graph, ML, experiments, backtesting, generator) but NO frontend exists — zero React code, no `package.json`, no `vite.config.*`. Fase 0 deferred the frontend scaffold and it was never delivered. Users have no way to visualize or interact with the platform. Fase 14 creates the SPA dashboard that consumes all existing v1 APIs.

## 2. Scope

### In Scope
- Frontend scaffold: React 19 + Vite + Tailwind CSS (per `SYSTEM_ARCHITECTURE.md §4`)
- Project structure: `frontend/src/{pages,layouts,components,charts,hooks,services,store}`
- API service layer wrapping all existing `/api/v1/*` endpoints
- 12 dashboard modules (prioritized — see §5)
- Zustand stores for client-side state
- Recharts-based chart components for frequencies, gaps, averages, probability
- CORS integration (already configured: `localhost:5173`)
- Empty-state / stub UI for Tendencias and IA modules

### Out of Scope
- Backend `/dashboard/*` endpoints (API_SPECIFICATION.md §13) — **deferred indefinitely** (see §4)
- Backend work for Tendencias or IA modules
- Auth/JWT (v1 has none)
- SSR / Next.js
- Production deployment / Docker / nginx
- Fase 15 AI Assistant
- Fase 16 Performance, Fase 17 Testing, Fase 18 Documentation
- Any changes to `backend/` code, `openspec/changes/fase-13-generator/`, or other fase folders

## 3. Capabilities

### New Capabilities
- `frontend-scaffold`: React+Vite+Tailwind project setup, routing, layouts, API client, state management
- `dashboard-modules`: 12 page modules composing existing backend APIs into interactive views

### Modified Capabilities
None — no existing spec-level behavior changes.

## 4. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1: Stack | React 19 + Vite + Tailwind | `SYSTEM_ARCHITECTURE.md §4` mandates it. SPA without SSR need; Vite fast HMR; Tailwind for rapid styling. Next.js adds unnecessary SSR/routing complexity. |
| D2: Dashboard strategy | **Frontend composition** | Frontend calls each module's existing endpoints directly and composes views. NO backend `/dashboard/*` endpoints. Tradeoff: more client requests vs. zero backend coupling, no new backend code, leverages existing service boundaries. API_SPECIFICATION.md `/dashboard/*` endpoints remain aspirational — NOT part of this phase. |
| D3: Charts | Recharts | React-native, simple API, sufficient for bar/line/pie/heatmap. D3 is overkill; Chart.js requires imperative DOM. |
| D4: State management | Zustand | Lightweight, no boilerplate, perfect for dashboard slice state. Redux is overkill for this SPA. |
| D5: Graph visualization | `react-force-graph-2d` | Only needed for Redes module (network graphs). Loaded lazily. |
| D6: Tendencias / IA | **Stub pages with empty-state UI** | No backend exists for these. Showing "Coming in Fase 15" is honest and avoids scope creep. Tendencias partially served by statistics frequencies but full trend analysis is deferred. |
| D7: Generator integration | Real `/gen/*` endpoints only | `POST /gen/generate`, `GET /gen/combinations`, `POST /gen/snapshot`, `GET /gen/snapshots`. Mapping: Generate→`/gen/generate`, History→`/gen/snapshots`, Detail→`/gen/combinations?snapshot_id=`. Error codes: `GEN_NO_SELECTION` (404), `GEN_COUNT_INVALID` (422), `GEN_DUPLICATE_SNAPSHOT` (409), `GEN_SPACE_EXHAUSTED` (422). |
| D8: Module prioritization | 3-tier (see §5) | Reduces cognitive load; delivers value incrementally; validates scaffold early. |

## 5. Module Prioritization

### Tier 1 — Scaffold + Core Value (first deliverable)
| Module | Backend Endpoints | Charts |
|--------|-------------------|--------|
| Inicio (Home) | `GET /health`, `GET /version`, `GET /lotteries` | Status cards |
| Historial | `GET /lotteries`, `GET /draws`, `GET /draws/{id}` | Table + filters |
| Estadísticas | `POST /statistics/generate`, `GET /statistics/{code}/frequencies`, `/gaps`, `/averages` | Bar + line charts |
| Generador | `POST /gen/generate`, `GET /gen/combinations`, `POST /gen/snapshot`, `GET /gen/snapshots` | Combination table |

### Tier 2 — Analytical Depth
| Module | Backend Endpoints | Charts |
|--------|-------------------|--------|
| Monte Carlo | `POST /probability/generate`, `GET /probability/{code}/probabilities` | Distribution plots |
| Modelos | `POST /ml/train`, `GET /ml/models`, `GET /ml/metrics` | Metrics table |
| Experimentos | 7 endpoints: CRUD + run + compare + export | Comparison charts |
| Backtesting | `POST /backtesting/run`, `GET /backtesting/history`, `GET /backtesting/results` | Walk-forward plots |

### Tier 3 — Visualization + Stubs
| Module | Backend Endpoints | Charts |
|--------|-------------------|--------|
| Heatmaps | `POST /graph/compute`, `GET /graph/{code}/snapshots` | Heatmap grid |
| Redes | `POST /graph/compute`, `GET /graph/{code}/snapshots` (graph_type=network) | Force-directed graph |
| Tendencias | **Stub** — no backend | Empty state: "Coming in future phase" |
| IA | **Stub** — no backend | Empty state: "Fase 15 — AI Assistant" |

## 6. Frontend Structure

```
frontend/
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── index.html
├── postcss.config.js
└── src/
    ├── main.tsx                    # React root + router
    ├── App.tsx                     # Route definitions
    ├── index.css                   # Tailwind directives
    ├── layouts/
    │   └── DashboardLayout.tsx     # Sidebar + header + content area
    ├── pages/
    │   ├── Home.tsx
    │   ├── History.tsx
    │   ├── Statistics.tsx
    │   ├── Generator.tsx
    │   ├── MonteCarlo.tsx
    │   ├── Models.tsx
    │   ├── Experiments.tsx
    │   ├── Backtesting.tsx
    │   ├── Heatmaps.tsx
    │   ├── Networks.tsx
    │   ├── Trends.tsx              # Stub
    │   └── AI.tsx                  # Stub
    ├── components/
    │   ├── Sidebar.tsx
    │   ├── Header.tsx
    │   ├── DataTable.tsx
    │   ├── EmptyState.tsx
    │   └── ErrorBoundary.tsx
    ├── charts/
    │   ├── FrequencyChart.tsx
    │   ├── GapChart.tsx
    │   ├── AverageChart.tsx
    │   ├── DistributionChart.tsx
    │   └── HeatmapChart.tsx
    ├── hooks/
    │   ├── useApi.ts               # Generic fetch hook
    │   └── useLotteries.ts
    ├── services/
    │   ├── api.ts                  # Axios/fetch wrapper, envelope parser
    │   ├── lotteries.ts
    │   ├── draws.ts
    │   ├── statistics.ts
    │   ├── probability.ts
    │   ├── graph.ts
    │   ├── ml.ts
    │   ├── experiments.ts
    │   ├── backtesting.ts
    │   └── gen.ts                  # Generator — maps to /gen/* only
    └── store/
        ├── useAppStore.ts          # Global: selected lottery, sidebar state
        └── useModuleStore.ts       # Per-module cache/state
```

## 7. Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/` | **New** | Entire React SPA — scaffold, pages, components, services, store |
| `backend/src/backend/app/main.py` | None | CORS already configured for `localhost:5173` |
| `openspec/changes/fase-13-generator/` | None | Untouched — read-only reference for `/gen/*` contracts |
| `openspec/changes/fase-*/` | None | No other fase directories modified |

## 8. Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| N+1 API calls on dashboard load | Medium | Tier by module; lazy-load non-visible tabs; aggregate in `useApi` hook |
| Recharts insufficient for complex heatmaps | Low | Fall back to custom SVG or `echarts-for-react` for heatmap only |
| `react-force-graph` bundle size | Low | Lazy import; only loaded on Redes page |
| Scope creep into backend changes | Medium | Strict: zero backend modifications in Fase 14. Documented non-goal. |
| CORS / proxy issues in dev | Low | CORS already configured; Vite dev server on 5173 matches `allowed_origins` |

## 9. Rollback Plan

- **Git revert**: `git revert` the frontend commit(s). No backend changes to undo.
- **No data risk**: Frontend is pure read/write to existing APIs; no local persistence.
- **Vite cleanup**: Remove `frontend/` directory and any root-level config references.

## 10. Dependencies

- Backend running on `localhost:8000` with all v1 endpoints operational
- Node.js 18+ / npm or pnpm for frontend toolchain
- All backend engines (F1–F13) must be functional (they are — confirmed by exploration)

## 11. Success Criteria

- [ ] `npm run dev` starts Vite on `localhost:5173` without errors
- [ ] All 12 module pages render (stubs for Tendencias/IA)
- [ ] Tier 1 modules (Home, History, Statistics, Generator) fully functional with real API data
- [ ] Generator module calls `/gen/*` endpoints correctly with error handling
- [ ] Charts render real data from backend APIs
- [ ] No backend code modified
- [ ] CORS works (no proxy needed)
- [ ] Responsive layout (desktop-first, mobile-friendly)
