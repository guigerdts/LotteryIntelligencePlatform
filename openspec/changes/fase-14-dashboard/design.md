# Design: Fase 14 — Dashboard

## Technical Approach

Frontend-only SPA (React 19 + Vite + Tailwind) consuming existing `/api/v1/*`. Shared `apiClient` parses `SuccessEnvelope`, Zustand for global state. Tiered implementation.

---

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Dev proxy | CORS only | Vite proxy | Backend allows `localhost:5173` |
| lottery mapping | `GET /lotteries` → store `{id, code}` | Client enum | Dynamic; no rebuild |
| Graph schema | `GraphValuesResponse` (float) | `GraphMetrics` (Decimal str) | Only API-exposed read path |
| Force graph | `React.lazy` + Vite import | Eager | Keeps main bundle small |
| UI | Custom Tailwind | Radix/shadcn | Minimal deps |
| State | Zustand `persist` (localStorage) | SessionStorage | R4 cross-session |
| Linter | ESLint + Prettier | Ruff (Python) | JS/TS tooling |
| Test | Vitest + RTL + MSW | Jest | Vite-native |

---

## Data Flow

```
Browser → Vite (5173) ─CORS→ FastAPI (8000) /api/v1/*
  → apiClient → Zustand (lotteryId+code, persisted) → Page hooks → render
```

---

## Directory Structure

```
frontend/src/
├── types/        envelope, lottery, draw, statistics, probability, graph, ml, experiment, backtesting, gen
├── services/     api.ts (apiClient), per-domain service files
├── store/        useLotteryStore (persist), useUIStore
├── hooks/        useApi, useLotteries
├── layouts/      DashboardLayout
├── components/   Sidebar, Header, NavGroup, NavItem, LotterySelector, LoadingState, EmptyState, ErrorState
├── charts/       FrequencyChart, GapChart, AverageChart, DistributionChart, HeatmapChart
├── pages/        Home, History, Statistics, Heatmaps, Networks (lazy), Trends (stub), MonteCarlo, AI (stub), Models, Experiments, Backtesting, Generator
└── test/         Vitest + MSW
```

Root: `package.json`, `vite.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `tsconfig.*.json`, `index.html`, `.env.example`

---

## Navigation

| Category | Route | Stub |
|----------|-------|------|
| General | `/`, `/historial` | No |
| Análisis | `/estadisticas`, `/heatmaps`, `/tendencias` | Tendencias |
| Avanzado | `/monte-carlo`, `/redes`, `/ia` | IA |
| ML | `/modelos`, `/experimentos`, `/backtesting` | No |
| Generador | `/generador` | No |

---

## Interfaces

### apiClient

```typescript
interface Envelope<T> { success: true; data: T; timestamp: string }
interface ErrorEnvelope { success: false; error: { code: string; message: string }; timestamp: string }
class AppError extends Error { code: string; status: number; }
// HTTP: 404→NotFoundError, 409→ConflictError, 422→ValidationError, 500+→ServerError
```

### useLotteryStore

```typescript
interface LotteryOption { id: number; code: string; name: string; country: string }
// persist: 'lip:selectedLottery' — partialize selectedId + selectedCode
// loadLotteries() → GET /lotteries; setSelected(id, code)
```

### lottery_id vs lottery_code

- **code**: statistics, probability, graph, draws
- **id**: ml, backtesting, experiment, gen
- Store holds both; service reads correct field.

---

## Backend Contracts

All: `SuccessEnvelope {success, data, timestamp}`.

| Endpoint | Method | Params | Response |
|----------|--------|--------|----------|
| `/lotteries` | GET | page, page_size | `list[LotteryRead]` |
| `/draws` | GET | lottery(code), order, page | `list[DrawRead]` |
| `/statistics/generate` | POST | `{lottery_code, metrics, scope}` | `GenerateSnapshot` |
| `/statistics/{code}/freq\|gaps\|avg` | GET | last | typed lists |
| `/probability/generate` | POST | `{lottery_code, model_set, scope}` | `GenerateSnapshot` |
| `/probability/{code}/probabilities` | GET | model, subject, last | `ProbabilityList` |
| `/graph/compute` | POST | `{lottery_code, graph_type}` | `ComputeSnapshot` |
| `/graph/{code}/snapshots/{id}` | GET | — | `GraphValuesResponse` (float) |
| `/ml/train\|models\|metrics` | POST/GET | lottery_id(int) | dict |
| `/experiment/create`, `/{id}/run\|compare` | POST | lottery_id(int) | typed |
| `/backtesting/run` | POST | `{lottery_id, strategy_id, ...}` | `BtRunResponse` |
| `/gen/generate` | POST | `{lottery_id, count?, seed?}` | `GenerationResult` |
| `/gen/combinations\|snapshots` | GET | lottery_id(int) | lists |
| `/gen/snapshot` | POST | `{lottery_id, snapshot_id, status}` | `SnapshotResult` |

---

## Page Compositions

- **Home**: Latest 5 draws, top-5 freq/least-freq, health/version. Skeletons/empty/error.
- **History**: Paginated table → detail (`GET /draws/{id}`).
- **Statistics**: Tabbed freq/gaps/averages. Generate button. Bar/line/bar.
- **Heatmaps**: Compute → snapshot → SVG grid.
- **Networks**: Lazy `react-force-graph-2d`. Nodes=numbers, links=weight.
- **Monte Carlo**: Generate → results table.
- **Models**: Models + metrics. Train button.
- **Experiments**: List/create/run/compare (`lottery_id`).
- **Backtesting**: Form → run. History + results.
- **Generator**: Inline form → result. Snapshots. GEN_* errors mapped.
- **Tendencias/IA**: `EmptyState` stubs.

---

## GEN_* Error Mapping

| Code | HTTP | Message |
|------|------|---------|
| `GEN_NO_SELECTION` | 404 | No active selection for this lottery |
| `GEN_NO_DISTRIBUTION` | 404 | No distribution available |
| `GEN_LOTTERY_NOT_FOUND` | 404 | Lottery not found |
| `GEN_COUNT_INVALID` | 422 | Count must be between 1 and 100 |
| `GEN_SNAPSHOT_NOT_FOUND` | 404 | Snapshot not found |
| `GEN_DUPLICATE_SNAPSHOT` | 409 | Snapshot already exists |
| `GEN_SPACE_EXHAUSTED` | 422 | Generation space exhausted |

---

## Testing / Responsive / Threats

- **Testing**: Unit (Vitest): apiClient, store, charts. Integration (MSW+RTL): pages, selector flow.
- **Responsive**: Sidebar `< md`. Charts `role="img"` + `aria-label`. WCAG AA.
- **Threat Matrix**: N/A.

## Migration

No migration. Frontend-only; `git revert` suffices.

---

## Tiers

**Tier 1**: scaffold, apiClient, types, stores, layout, router, Home, History, Statistics, Generator.

**Tier 2**: MonteCarlo, Models, Experiments, Backtesting.

**Tier 3**: Heatmaps, Networks (lazy), Trends (stub), AI (stub).

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Force graph lazy fails | WARNING | Test Tier 3 early; eager fallback |
| lottery_id/code mismatch | WARNING | Store holds both; typed interface |
| Bundle size > NFR-8 | INFO | Lazy per route; graph on `/redes` only |

## Open Questions

None — all resolved from proposal + spec + backend verification.
