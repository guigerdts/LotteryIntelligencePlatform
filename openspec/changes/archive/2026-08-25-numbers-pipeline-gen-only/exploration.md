# Exploration: numbers-pipeline-gen-only

## Current State

The `POST /api/v1/pipeline/numbers` endpoint runs an 8-stage chain defined by `STAGE_ORDER = ("stats","features","ml","dl","bt","rank","select","gen")` in `pipeline_service.py`. After the prior `number-generation-remix` change, `gen` no longer consumes meta outputs — it reads only the active probability snapshot (F5) + draw stats. Stages `ml/dl/bt/rank/select` still execute but report `skipped / active artifact reused` because their artifacts exist. The frontend mirrors this 8-stage order in its type system and test assertions, contradicting the honest UI subtitle ("stats → probabilidad F5 → generate").

**Confirmed `STAGE_ORDER` values (backend):** `("stats","features","ml","dl","bt","rank","select","gen")`

**`_DEPS`:** `{"ml": ("stats","features"), "bt": ("stats",)}` — only relevant to the meta stages being removed.

**`_GATED_STAGES`:** `frozenset({"ml","bt"})` — also meta-specific.

**`/numbers` is the SOLE production consumer** of `PipelineService`. Only `api/v1/pipeline.py` imports it (1 occurrence in `src/`; 18 occurrences in `tests/`). The backtesting UI has its own `api/v1/bt.py` endpoint. `runNumbersPipeline` is called exclusively from `MisNumeros.tsx`.

## Affected Areas

- `backend/src/backend/app/services/pipeline_service.py` — reduce `STAGE_ORDER` to `("stats","features","gen")`, remove `ml/dl/bt/rank/select` from `_execute_stage`, remove `_DEPS`/`_GATED_STAGES` (no longer needed for a 3-stage chain with no gated writers), remove `_run_rank`, `_ranking_stale`, `_safe_context_hash`, `derive_context_hash`, and the adapter classes (`_MlDrawAdapter` etc.).
- `frontend/src/types/pipeline.ts` — reduce `PipelineStageName` union to `"stats"|"features"|"gen"`.
- `frontend/src/pages/MisNumeros.test.tsx` — update `STAGE_ORDER` constant (line 15), fix assertion `toHaveLength(8)` (line 115), update R2 test (line 165) and `failedRankStages` helper.
- `backend/tests/pipeline/` — 5 test files reference 8-stage behavior; need updating for 3-stage chain.

## Approaches

1. **Backend chain reduction + frontend alignment (Recommended)**
   - Pros: Backend stops wasting compute on dead stages; frontend truthfully reflects reality; single source of truth in `STAGE_ORDER`.
   - Cons: Touches backend + frontend + tests; medium blast radius.
   - Effort: Medium

2. **Frontend-only filter (NOT recommended)**
   - Pros: No backend changes.
   - Cons: Backend still runs 5 wasted stages per request (minutes-scale latency); frontend type/test mismatch with actual API; dishonest — hides the waste rather than removing it.
   - Effort: Low

## Recommendation

Approach A. The meta stages (`ml/dl/bt/rank/select`) are dead weight in the numbers path — `gen` was decoupled by `number-generation-remix` and reads only probability + stats. Removing them from the chain reduces latency, simplifies the service, and makes frontend/backend consistent.

## Risks

- **Backend tests**: 5 test files in `backend/tests/pipeline/` assert 8-stage behavior; all must be rewritten. Mitigated by the existing `run_chain` fixture which delegates to `PipelineService.run()`.
- **Backtesting/experiment independence**: Confirmed — `api/v1/bt.py` is a separate endpoint; no experiment UI calls `/numbers`.
- **`gen` dependency on selection**: `GenService._resolve_selection()` still requires an active `MetaSelection`. This is a read-only lookup, NOT part of the pipeline chain — `gen` looks it up independently. No risk.

## Ready for Proposal

Yes.
