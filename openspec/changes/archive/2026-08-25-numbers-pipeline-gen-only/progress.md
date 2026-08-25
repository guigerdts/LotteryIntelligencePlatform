# Apply Progress: Numbers Pipeline — Gen-Only Chain

## Completed Tasks

- [x] 1.1 **(RED)** Add test in `tests/pipeline/test_pipeline_failures.py`: monkeypatch `FeatureEngineService.generate` to raise; assert `PIPE_STAGE_FAILED("features")`, `gen` never runs, `stats` persist. (REQ-01)
- [x] 1.2 **(GREEN)** `pipeline_service.py`: rewrite `STAGE_ORDER` to `("stats","features","gen")`; delete `_DEPS`, `_GATED_STAGES`, `_gated_skip`, `_safe_context_hash`, `_RunState.context_hash`, `derive_context_hash`, `_run_rank`, `_ranking_stale`, `_naive`, `BT_STRATEGY_ID`; remove rank/select context-hash from `run()`. (REQ-01)
- [x] 1.3 **(GREEN)** `_execute_stage`: delete `ml`/`dl`/`bt`/`rank`/`select` branches. (REQ-01)
- [x] 1.4 **(GREEN)** `_read_artifact`: delete `ml`/`dl`/`bt`/`rank`/`select` branches; remove `context_hash` parameter. (REQ-01)
- [x] 1.5 **(GREEN)** Delete 4 adapter classes, `_naive`, update module docstring. (REQ-01)
- [x] 2.1 **(RED)** Add test: pipeline on fresh DB with no `MetaSelection` → `gen` completes successfully. (REQ-01 scenario: gen without MetaSelection)
- [x] 2.2 **(GREEN)** `_resolve_selection`: when no active `MetaSelection`, query active `ProbSnapshot`, return `SimpleNamespace(id=0, fingerprint=sha256(canonical_json({checksum, lottery_id})))`. (REQ-01)
- [x] 3.1 `api/v1/pipeline.py`: update docstring to 3-stage chain. (REQ-03)
- [x] 3.2 `types/pipeline.ts`: `PipelineStageName` → `"stats"|"features"|"gen"`. (REQ-03)
- [x] 4.1 `conftest.py`: `STAGE_ORDER` → 3; trim `stage_recorder`/`clear_stages`/`artifact_versions` to 3 stages; remove `fast_dl_training`/`fast_ml_training`.
- [x] 4.2 `test_pipeline_cold_chain.py`: assert 3 stages in order; remove bt-before-rank. (REQ-01)
- [x] 4.3 `test_pipeline_healing.py`: new 3-row matrix. (REQ-02)
- [x] 4.4 `test_pipeline_failures.py`: replace `fail_rank` with `fail_features`. (REQ-01)
- [x] 4.5 `test_pipeline_idempotent.py`: 3-stage artifact versions.
- [x] 4.6 Delete `test_pipeline_context.py` (bt-before-rank, N/A).
- [x] 4.7 Delete `test_pipeline_autotrain.py` (ml/dl auto-train, N/A).
- [x] 4.8 `MisNumeros.test.tsx`: `STAGE_ORDER` → 3; `toHaveLength(3)`; replace `failedRankStages` with `failedFeaturesStages`.
- [x] 5.1 `backend/.venv/bin/pytest tests/pipeline/ -x -v` — all pass.
- [x] 5.2 `backend/.venv/bin/pytest tests/gen/ -x -v` — no regressions.
- [x] 5.3 `cd frontend && npm test` — MisNumeros tests pass.
- [x] 5.4 `cd frontend && npx tsc -b --noEmit` — no type errors.
- [x] 5.5 `ruff check` on changed backend files — clean.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `test_pipeline_failures.py` | Unit | ✅ 14/14 | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 2.1 | `test_pipeline_failures.py` | Unit | ✅ 14/14 | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `backend/src/backend/app/services/pipeline_service.py` | Modified | Reduced to 3-stage pipeline, removed dead code |
| `backend/src/backend/app/services/gen_service.py` | Modified | Added deterministic fallback for no MetaSelection |
| `backend/src/backend/app/api/v1/pipeline.py` | Modified | Updated docstring to 3-stage |
| `frontend/src/types/pipeline.ts` | Modified | PipelineStageName → 3 values |
| `backend/tests/pipeline/conftest.py` | Modified | Updated for 3-stage pipeline |
| `backend/tests/pipeline/test_pipeline_failures.py` | Modified | Added gen fallback test |
| `backend/tests/pipeline/test_pipeline_cold_chain.py` | Modified | Updated for 3 stages |
| `backend/tests/pipeline/test_pipeline_healing.py` | Modified | New 3-row matrix |
| `backend/tests/pipeline/test_pipeline_idempotent.py` | Modified | No changes needed |
| `backend/tests/pipeline/test_pipeline_context.py` | Deleted | bt-before-rank tests no longer applicable |
| `backend/tests/pipeline/test_pipeline_autotrain.py` | Deleted | ml/dl auto-train tests no longer applicable |
| `frontend/src/pages/MisNumeros.test.tsx` | Modified | Updated for 3 stages |
| `backend/tests/gen/test_gen_api.py` | Modified | Updated no-selection test |
| `backend/tests/gen/test_gen_generate.py` | Modified | Updated no-selection test |
