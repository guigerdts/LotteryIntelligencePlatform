# Tasks: Fase 14 — Dashboard

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High
PR split: PR 1 (~350) → PR 2 (~550) → PR 3 (~500) → PR 4 (~400)

## Phase 1: Foundation

- [ ] T1-01 Scaffold `frontend/`: package.json, vite.config.ts, tailwind, postcss, tsconfigs, index.html, src/{main,App,index.css}. [R1] deps: none. **Verify**: `npm run dev` starts on :5173.
- [ ] T1-02 Create `src/types/{envelope,lottery,draw,statistics,probability,graph,ml,experiment,backtesting,gen}.ts`. [R6] deps: T1-01. **Verify**: tsc no errors.
- [ ] T1-03 Create `src/services/api.ts` — apiClient: VITE_API_BASE_URL, parse Envelope, map 404/409/422/500+. [R5] deps: T1-02. **Verify**: api.test.ts passes.
- [ ] T1-04 Create `src/services/{lotteries,draws,statistics,probability,graph,ml,experiments,backtesting,gen}.ts`. [R5] deps: T1-03. **Verify**: tsc.
- [ ] T1-05 Create `src/store/useLotteryStore.ts` — Zustand persist (lip:selectedLottery): id, code, loadLotteries, setSelected. [R4, R19] deps: T1-03. **Verify**: store.test.ts passes.
- [ ] T1-06 Create `src/store/useModuleStore.ts`. [R19] deps: T1-01. **Verify**: tsc.
- [ ] T1-07 Create `src/hooks/{useApi,useLotteries}.ts`. [R4, R20] deps: T1-03, T1-05. **Verify**: tsc.

## Phase 2: Core UI + Tier 1

- [ ] T2-01 Create `src/layouts/DashboardLayout.tsx` + `src/components/{Sidebar,Header}.tsx`. [R3, R4] deps: T1-05, T1-07. **Verify**: sidebar renders 5 nav groups, selector calls /lotteries.
- [ ] T2-02 Create `src/components/{DataTable,EmptyState,ErrorState,Skeleton}.tsx`. [R20] deps: T1-01. **Verify**: TypeScript compiles.
- [ ] T2-03 Create `src/pages/Home.tsx` — draws, freq summary, health. [R7] deps: T2-01, T2-02. **Verify**: MSW test renders draws+freq+health.
- [ ] T2-04 Create `src/pages/History.tsx` — draw list + detail. [R8] deps: T2-01, T2-02. **Verify**: MSW test renders draw list.
- [ ] T2-05 Create `src/pages/Statistics.tsx` — freq/gaps/averages + generate. [R9] deps: T2-01, T2-02. **Verify**: MSW test: generate + charts render.
- [ ] T2-06 Create `src/pages/Generator.tsx` — form→generate→result + GEN_* errors. [R18] deps: T2-01, T2-02. **Verify**: MSW test: generate inline, GEN_COUNT_INVALID error.
- [ ] T2-07 Configure `src/App.tsx` — createBrowserRouter, 12 routes, lazy+Suspense, 404. [R2] deps: T2-01 through T2-06. **Verify**: `npm run build` zero errors.

## Phase 3: Tier 2 + Tier 3 Pages

- [ ] T3-01 Create `src/pages/MonteCarlo.tsx`. [R13] deps: T2-07. **Verify**: MSW test renders probability table.
- [ ] T3-02 Create `src/pages/Models.tsx`. [R15] deps: T2-07. **Verify**: MSW test renders model list.
- [ ] T3-03 Create `src/pages/Experiments.tsx`. [R16] deps: T2-07. **Verify**: MSW test: create+list.
- [ ] T3-04 Create `src/pages/Backtesting.tsx`. [R17] deps: T2-07. **Verify**: MSW test: run+results.
- [ ] T3-05 Create `src/pages/Heatmaps.tsx`. [R10] deps: T2-07. **Verify**: MSW test renders heatmap grid.
- [ ] T3-06 Create `src/pages/Networks.tsx` — React.lazy force-graph. [R11] deps: T2-07. **Verify**: lazy import verified (not in main bundle).
- [ ] T3-07 Create `src/pages/{Trends,AI}.tsx` — EmptyState stubs. [R12, R14] deps: T2-07. **Verify**: no API calls, empty state renders.

## Phase 4: Charts + Verification

- [ ] T4-01 Create `src/charts/{FrequencyChart,GapChart,AverageChart,DistributionChart,HeatmapChart}.tsx`. [R23] deps: T1-02. **Verify**: TypeScript compiles, typed props match backend shapes.
- [ ] T4-02 Verify: charts role="img"+aria-label, sidebar < md, WCAG AA, VITE_API_BASE_URL. [R22, R24] deps: T2-01, T4-01. **Verify**: axe-core passes, viewport test.
- [ ] T4-03 Create `src/test/setup.ts` + tests: api.test.ts, useLotteryStore.test.ts, Home/Statistics/Generator/Trends/AI.test.tsx. [R5, R7, R9, R12, R14, R18] deps: T1-03, T1-05, T2-03 through T2-06, T3-07. **Verify**: `npx vitest run` all pass.
- [ ] T4-04 Verify: `npm run build` zero errors, `git diff backend/` zero changes, all 12 routes render. [NFR-1,3,4] deps: all. **Verify**: build exit code 0, diff empty.
