# Tasks: Numbers Pipeline — Gen-Only Chain

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~280 (150 additions, ~130 net deletions) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Delivery strategy | ask-on-risk |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

## Phase 1: Backend pipeline_service.py

- [x] 1.1 **(RED)** Add test in `tests/pipeline/test_pipeline_failures.py`: monkeypatch `FeatureEngineService.generate` to raise; assert `PIPE_STAGE_FAILED("features")`, `gen` never runs, `stats` persist. (REQ-01)
- [x] 1.2 **(GREEN)** `pipeline_service.py`: rewrite `STAGE_ORDER` to `("stats","features","gen")`; delete `_DEPS`, `_GATED_STAGES`, `_gated_skip`, `_safe_context_hash`, `_RunState.context_hash`, `derive_context_hash`, `_run_rank`, `_ranking_stale`, `_naive`, `BT_STRATEGY_ID`; remove rank/select context-hash from `run()`. (REQ-01)
- [x] 1.3 **(GREEN)** `_execute_stage`: delete `ml`/`dl`/`bt`/`rank`/`select` branches. (REQ-01)
- [x] 1.4 **(GREEN)** `_read_artifact`: delete `ml`/`dl`/`bt`/`rank`/`select` branches; remove `context_hash` parameter. (REQ-01)
- [x] 1.5 **(GREEN)** Delete 4 adapter classes, `_naive`, update module docstring. (REQ-01)

## Phase 2: Backend gen_service.py

- [x] 2.1 **(RED)** Add test: pipeline on fresh DB with no `MetaSelection` → `gen` completes successfully. (REQ-01 scenario: gen without MetaSelection)
- [x] 2.2 **(GREEN)** `_resolve_selection`: when no active `MetaSelection`, query active `ProbSnapshot`, return `SimpleNamespace(id=0, fingerprint=sha256(canonical_json({checksum, lottery_id})))`. (REQ-01)

## Phase 3: Frontend + API docstring

- [x] 3.1 `api/v1/pipeline.py`: update docstring to 3-stage chain. (REQ-03)
- [x] 3.2 `types/pipeline.ts`: `PipelineStageName` → `"stats"|"features"|"gen"`. (REQ-03)

## Phase 4: Test rewrites

- [x] 4.1 `conftest.py`: `STAGE_ORDER` → 3; trim `stage_recorder`/`clear_stages`/`artifact_versions` to 3 stages; remove `fast_dl_training`/`fast_ml_training`.
- [x] 4.2 `test_pipeline_cold_chain.py`: assert 3 stages in order; remove bt-before-rank. (REQ-01)
- [x] 4.3 `test_pipeline_healing.py`: new 3-row matrix. (REQ-02)
- [x] 4.4 `test_pipeline_failures.py`: replace `fail_rank` with `fail_features`. (REQ-01)
- [x] 4.5 `test_pipeline_idempotent.py`: 3-stage artifact versions.
- [x] 4.6 Delete `test_pipeline_context.py` (bt-before-rank, N/A).
- [x] 4.7 Delete `test_pipeline_autotrain.py` (ml/dl auto-train, N/A).
- [x] 4.8 `MisNumeros.test.tsx`: `STAGE_ORDER` → 3; `toHaveLength(3)`; replace `failedRankStages` with `failedFeaturesStages`.

## Phase 5: Verification

- [x] 5.1 `backend/.venv/bin/pytest tests/pipeline/ -x -v` — all pass.
- [x] 5.2 `backend/.venv/bin/pytest tests/gen/ -x -v` — no regressions.
- [x] 5.3 `cd frontend && npm test` — MisNumeros tests pass.
- [x] 5.4 `cd frontend && npx tsc -b --noEmit` — no type errors.
- [x] 5.5 `ruff check` on changed backend files — clean.
