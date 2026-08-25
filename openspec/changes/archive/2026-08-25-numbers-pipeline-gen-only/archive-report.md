# Archive Report — numbers-pipeline-gen-only

## Status
**CLOSED / ARCHIVED** — 2026-08-25

## Summary
Reduced the `/numbers` generation pipeline from the 8-stage canonical chain
(`stats → ml → dl → features → bt → rank → select → gen`) to a lean
**3-stage chain** (`stats → features → gen`), and decoupled `gen` from requiring
an active `MetaSelection`.

## Deliverables
- **PR #74** `feat/numbers-pipeline-gen-only-core` → `main`
  - `backend/src/backend/app/services/pipeline_service.py`: `STAGE_ORDER = ("stats", "features", "gen")`; removed meta stages, gated-stage logic, and adapter classes.
  - `backend/src/backend/app/services/gen_service.py`: `_resolve_selection` now falls back to `id=0` + a deterministic fingerprint `sha256(f"{ProbSnapshot.checksum}|{lottery_id}")` when no active `MetaSelection` exists (preserves `GEN-008` idempotency).
  - `backend/src/backend/app/api/v1/pipeline.py`: docstring updated.
- **PR #75** `feat/numbers-pipeline-gen-only-tests` → `core` (landed on `main`)
  - Backend `tests/pipeline/*` rewritten to the 3-stage contract; deleted `test_pipeline_context.py` (bt-before-rank) and `test_pipeline_autotrain.py` (ml/dl auto-train).
  - Added test that `gen` succeeds **without** an active `MetaSelection`.
  - `frontend/src/types/pipeline.ts`: `PipelineStageName` = 3 values; `MisNumeros.test.tsx` updated.

## Scope Notes
- Engines `ml/dl/bt/opt/feature` are **kept** (consumed by backtesting / experiment UIs). They were only removed from the `/numbers` path.
- `/numbers` is the sole `PipelineService` consumer; backtesting uses `api/v1/bt.py`.

## Verification
- Strict TDD: backend (`pytest`) + frontend (`npm test`) + `tsc -b` + `eslint` green across both PRs (22/22 tasks).
- Manual: app testable against seeded `database/lip.db`; Mis Números returns 5 combinations with honest UI (subtitle + Transparencia + `Peso`).

## Reason for split
Single attempt was 793 changed lines (>400 review budget). Delivered as two stacked
PRs, each <400 lines (core 398, tests 395), per `ask-on-risk` → split decision.

## Artifacts
- `proposal.md`, `specs/`, `design.md`, `tasks.md`, `exploration.md`, `progress.md` moved to `openspec/changes/archive/2026-08-25-numbers-pipeline-gen-only/`.
