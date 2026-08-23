# Proposal: Deep Learning Frontend Page

## Intent

The DL API (`/api/v1/dl`, FINAL on main) has no UI: snapshots, metrics, training unreachable from the frontend. Add a Deep Learning page at `/dl` mirroring the ML Models page for parity.

## Goals / Non-Goals

Goals: read snapshots + per-model metrics for the selected lottery; manual train trigger with persistent busy state; full `Models.tsx` state parity (Skeleton / ErrorState / EmptyState / DataTable).

Non-goals:
- NO backend edits — contract is final.
- NO `apiClient`/`useApi` refactors; no ETag conditional requests.
- NO window/cut inputs in v1 (`window=10`, `cut=auto` defaults).
- No polling of the ~100s sync train call.

## Scope

In scope:
- `frontend/src/services/dl.ts` — getDlModels/getDlMetrics/trainDlModels mirroring `ml.ts`.
- `frontend/src/types/dl.ts` — DLSnapshot (adds `window` vs MLSnapshot), DLMetric, DLTrainResult/Row.
- `frontend/src/pages/DL.tsx` — mirrors `Models.tsx` + Models-precedent Train button.
- `frontend/src/pages/DL.test.tsx` — vitest + Testing Library + MSW handlers for `/dl/*`.
- Route `/dl` (lazy import, `App.tsx`) + "Deep Learning" entry in Sidebar ML group.

Out of scope: ETag caching; useApi error-code preservation; window/cut inputs (v2); nav icons.

## Capabilities

### New Capabilities
- `dl-frontend-page`: frontend DL read/train surface — typed service client, page UI states, routing/nav entry.

### Modified Capabilities
- None (`dl-engine` backend spec unchanged).

## Approach

Exploration **Approach 1**: mirror `Models.tsx`/`ml.ts` 1:1 — maximal consistency, lowest review cost, proven MSW test pattern; page-level duplication accepted convention. SNAPSHOT_NOT_FOUND renders as empty state + Train CTA (Models precedent): `useApi` flattens error codes and shared-layer changes are excluded from v1.

## Affected Areas

- `frontend/src/services/dl.ts` — New, ~35 ln.
- `frontend/src/types/dl.ts` — New, ~30 ln.
- `frontend/src/pages/DL.tsx` — New, ~150 ln.
- `frontend/src/pages/DL.test.tsx` — New, ~120–150 ln.
- `frontend/src/App.tsx` — Modified, +2 ln (route).
- `frontend/src/components/Sidebar.tsx` — Modified, +1 ln (nav).

## Risks

- Sync POST `/dl/train` blocks ~100s (High) — persistent busy state, disabled button; documented UX limit.
- Recorded inconsistency: `parseResponse` calls `response.json()` unconditionally — a 304 would throw (deferred); no If-None-Match in v1; apiClient fix later.
- Diff straddles 400-line review budget (Medium) — see Delivery.

## Delivery

Forecast **~350–450 authored lines incl. tests** → budget risk: Medium. Chained PRs recommended: No — single PR if tasks-phase count ≤400; else pre-approved split: PR1 service+types (~70), PR2 page+route+nav+tests (~330). Decision needed before apply: No; final forecast: sdd-tasks.

## Rollback Plan

Fully additive: delete four new files, revert two edits. No schema/data/shared-layer impact; other pages unaffected.

## Dependencies

- Backend `/api/v1/dl` on main; dev servers running for smoke.

## Success Criteria

- vitest green: models + metrics render, empty→Train CTA, train busy→refetch, failed rows (MSW).
- Frontend lint/format pass.
- Manual smoke on dev servers: `/dl` + sidebar entry live, lottery selection drives queries, real train run completes and refreshes lists.
