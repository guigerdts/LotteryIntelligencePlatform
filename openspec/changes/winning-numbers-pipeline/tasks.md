# Tasks: Winning Numbers Pipeline (Baloto/Revancha)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | S1 ≈430 · S2 ≈330 · S3 ≈390 (design forecasts) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1 generator-output) → PR 2 (S2 numbers-orchestrator) → PR 3 (S3 mis-numeros-page) |
| Delivery strategy | auto-chain — owner-ratified 3 stacked-to-main PRs |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Per-Slice Budget Verdict

| Slice | Forecast | Authored est. | Verdict vs 400 |
|-------|----------|---------------|----------------|
| S1 | ≈430 | ≈360 (regenerated goldens excluded from authored count) | Pass, medium margin |
| S2 | ≈330 | ≈330; worst-case ≈560 if healing matrix is not parametrized | Pass — keep matrix parametrized; if diff >400 at PR-open, split service/endpoint commits into PR 2a/2b |
| S3 | ≈390 | ≈390 incl −235 Generator deletion | Borderline pass |

Threat matrix: N/A per design (single internal FastAPI route behind existing envelope/error handlers) — no threat-driven RED tasks.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Legal combo + reproducible SB + non-null score, v2 identity | PR 1 | `cd backend && .venv/bin/pytest tests/gen -v` | Seeded end-to-end generate via API test client (`tests/gen/test_gen_api.py`) | Revert PR 1 → generator back to v1 null-SB output |
| 2 | Orchestrator chain, healing matrix, endpoint | PR 2 | `cd backend && .venv/bin/pytest tests/pipeline -v` | Cold-chain service-layer run on seeded SQLite fixture (`tests/pipeline/conftest.py`) | Revert PR 2 → additive files removed, router unmounted; stage-service internals untouched |
| 3 | MyNumbers page replaces Generator form | PR 3 | `cd frontend && npx vitest run src/pages/MyNumbers.test.tsx` | MSW-mocked render scenarios in jsdom (`MyNumbers.test.tsx`) | Revert PR 3 → `Generator.tsx` restored, route reverted |

## SLICE S1 = PR 1 — generator-output (`feat(gen)`)

### Phase 1: RED — failing tests first

- [x] 1.1 RED `backend/tests/gen/test_sampling.py`: sampling returns `(combo, sb)`; SB drawn once per **accepted** combo on the SAME `isolated_rng(seed)` stream (D1); SB integer ∈ 1–16. Verify: `cd backend && .venv/bin/pytest tests/gen/test_sampling.py -v`
- [x] 1.2 RED `backend/tests/gen/test_validation.py`: `validate_combination(numbers, None, cfg)` → False; out-of-range SB → False (D5). Verify: `cd backend && .venv/bin/pytest tests/gen/test_validation.py -v`
- [x] 1.3 RED `backend/tests/gen/test_gen_generate.py`: duplicate `[7,7,12,30,41]` → `GEN_INVALID_NUMBERS`; bad SB → `GEN_INVALID_SUPER_NUMBER`; zero imported draws → `GEN_NO_HISTORY`; all three persist nothing (R1/R2). Verify: `cd backend && .venv/bin/pytest tests/gen/test_gen_generate.py -v`
- [x] 1.4 RED same file: every persisted row has finite `score == round(entry_score × mean(P(n)), 6)` (D3); responses echo non-null `super_number`/`score` (R3).
- [x] 1.5 RED `backend/tests/gen/test_types.py`: version assert == `"2.0.0"`; preserve pre-change fixture fingerprints, assert no new fingerprint aliases one; legacy NULL-SB rows still deserialize (D6/R2).
- [x] 1.6 RED `backend/tests/gen/test_gen_schemas.py` + `test_gen_api.py`: non-null echo typing; `_CODE_TO_STATUS` maps the 3 new codes → 422 (D10).

### Phase 2: GREEN — implementation

- [x] 2.1 `generators/validation.py`: False when `sb is None`/out-of-range (D5, +6/−4). Verify: `cd backend && .venv/bin/pytest tests/gen/test_validation.py tests/gen/test_sampling.py -v`
- [x] 2.2 `generators/sampling.py`: `(combo, sb)` return, sb-marginal param, post-acceptance draw on shared stream, pre-persist gate (D1/D5, +45/−12). Verify: `cd backend && .venv/bin/pytest tests/gen/test_sampling.py -v`
- [x] 2.3 `services/gen_service.py`: `_load_sb_marginal` (empirical over `SuperNumber.value`; uniform 1–16 when <32 obs; `GEN_NO_HISTORY` at zero — D2); D3 score computed where pools carry both inputs; persist sb+score replacing the `None` placeholders at `gen_service.py:167`; assert before `create_active_snapshot`. Verify: `cd backend && .venv/bin/pytest tests/gen/test_gen_generate.py -v`
- [x] 2.4 `services/errors.py` + `api/errors.py`: add `GEN_INVALID_NUMBERS`, `GEN_INVALID_SUPER_NUMBER`, `GEN_NO_HISTORY` + 422 status rows. Verify: `cd backend && .venv/bin/pytest tests/gen/test_gen_api.py -v`
- [x] 2.5 `schemas/gen.py`: enforce non-null `super_number`/`score` echo typing (±4). Verify: `cd backend && .venv/bin/pytest tests/gen/test_gen_schemas.py -v`

**Commits**: `feat(gen): sample reproducible Superbalota and gate legality pre-persist` (1.1–1.3, 2.1–2.2, 2.4) → `feat(gen): persist selection-weighted combination scores` (1.4, 2.3, 2.5).

### Phase 3: Goldens + regression gates

- [x] 3.1 Regenerate golden fixtures under v2 identity for existing seeds; aliasing-guard test green against preserved pre-change fingerprints; legacy-row read test green. Verify: `cd backend && .venv/bin/pytest tests/gen -v`
- [x] 3.2 Full regression: `cd backend && .venv/bin/pytest`
- [x] 3.3 Gates: `cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .`

**Commit**: `chore(gen): bump GENERATOR_VERSION to 2.0.0 with regenerated goldens` (1.5, 3.1 — identity change atomic with its goldens).

## SLICE S2 = PR 2 — numbers-orchestrator (`feat(pipeline)`)

### Phase 4: RED — service-layer tests (`backend/tests/pipeline/`, strict TDD)

- [ ] 4.1 Create `backend/tests/pipeline/conftest.py`: seeded-import SQLite fixture, service-layer harness (no HTTP), stage spies/instrumentation.
- [ ] 4.2 RED `test_pipeline_cold_chain.py` (R1/R3): one call runs `stats → features → ml → dl → bt → rank → select → gen` in canonical order, all 8 completed; ordered report entries carry allowed statuses + snapshot_id/fingerprint refs; combinations returned. Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_cold_chain.py -v`
- [ ] 4.3 RED `test_pipeline_healing.py::test_healing_matrix` (R2) — explicit parametrized rows, each asserting the EXACT skip/run set: `{}` cold; `{stats}`; `{stats,features}`; `{stats…bt}` (missing ml/dl/rank/select/gen); `{stats…rank}` (missing select/gen only); plus fresh-draw row: completed chain + 1 new draw → draw-coverage-dependent stages re-run, unaffected upstream skip. Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_healing.py -v`
- [ ] 4.4 RED `test_pipeline_idempotent.py` (R4): two identical runs → identical payloads; zero new snapshot versions in ANY store. Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_idempotent.py -v`
- [ ] 4.5 RED `test_pipeline_failures.py` (R1): forced rank failure → `PIPE_STAGE_FAILED` naming `rank`; `gen` never runs; earlier artifacts persist. Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_failures.py -v`
- [ ] 4.6 RED bt-before-rank context (D8): spies assert `bt` completes before `rank`; rank ctx derived from executed bt fingerprint via `resolve_context_vector` + `compute_context_hash` (no hardcoded hash — retires `meta_service.py:242`); stale ranking (`created_at` ≤ newest active BtSnapshot) triggers exactly ONE rerank, second failure → `PIPE_STAGE_FAILED(rank)`.
- [ ] 4.7 RED `test_pipeline_autotrain.py` (D12): missing ml/dl artifacts → `MlService.train`/`DlService.train` with registry defaults (`model_set="core"`, DL order `mlp→lstm`), chain proceeds. Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_autotrain.py -v`
- [ ] 4.8 RED `test_pipeline_api.py`: `POST /api/v1/pipeline/numbers` SuccessEnvelope; `PipelineRunRequest(lottery_id, count?, seed?)`; failed run → 502 with stage detail (D10). Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_api.py -v`

### Phase 5: GREEN — implementation

- [ ] 5.1 `services/pipeline_service.py` (+175): ordered stage runner; skip-vs-run decided by comparing active-artifact fingerprint before/after each call; D9 features stage runs FeatureEngine then Probability internally; D8 detect-and-rerank; D12 auto-train. Verify: `cd backend && .venv/bin/pytest tests/pipeline -v`
- [ ] 5.2 `schemas/pipeline.py` (+45): `PipelineRunRequest`, `PipelineStageResult(name,status∈{skipped,completed,failed},snapshot_id,fingerprint,error_code,detail)`, `PipelineRunResult(stages[8], result|None)`.
- [ ] 5.3 `api/v1/pipeline.py` (+55) + mount in `api/v1/router.py` (+2). Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_api.py -v`
- [ ] 5.4 `PIPE_STAGE_FAILED` in `services/errors.py` + 502 row in `api/errors.py` (+10). Verify: `cd backend && .venv/bin/pytest tests/pipeline/test_pipeline_api.py -v`

**Commits**: `feat(pipeline): add fingerprint-healing orchestrator for canonical chain` (4.1–4.7, 5.1) → `feat(pipeline): expose POST /pipeline/numbers with per-stage report` (4.8, 5.2–5.4).

### Phase 6: Regression gates

- [ ] 6.1 Meta regression (retired `:242` coupling): `cd backend && .venv/bin/pytest tests/meta -v`
- [ ] 6.2 Full regression: `cd backend && .venv/bin/pytest`
- [ ] 6.3 Gates: `cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .`

## SLICE S3 = PR 3 — mis-numeros-page (`feat(numbers-ui)`)

### Phase 7: RED — vitest+MSW (`frontend/src/pages/MyNumbers.test.tsx`)

- [ ] 7.1 RED R1: CTA click → exactly ONE POST to `/api/v1/pipeline/numbers`; zero calls to any stage endpoint (MSW request counters). Verify: `cd frontend && npx vitest run src/pages/MyNumbers.test.tsx`
- [ ] 7.2 RED busy/retry: delayed handler → CTA disabled with `aria-busy` during flight; then 500 → `ErrorState` Retry re-posts (DL page precedent).
- [ ] 7.3 RED stages (R2): 200 with 8 entries → all render in canonical order with statuses; failed `rank` shows its error, combinations absent, page stays interactive.
- [ ] 7.4 RED dual-draw (R3): tickets labeled “un boleto, dos sorteos (Baloto+Revancha)”; NO toggle/Baloto-vs-Revancha control anywhere in DOM.
- [ ] 7.5 RED count (R4/D11): untouched control → request body `count: 5`; control remains adjustable pre-run.
- [ ] 7.6 RED tiers (R5): tier table renders exactly the 8 official tiers (5+SB jackpot, 5, 4+SB, 4, 3+SB, 3, 2+SB paramutual, 0+SB refund).
- [ ] 7.7 RED disclaimer (R6): randomness disclaimer visible idle AND after generation.

### Phase 8: GREEN — implementation

- [ ] 8.1 `types/gen.ts` + `services/gen.ts`: pipeline stage/result types + `runNumbersPipeline()` (+32).
- [ ] 8.2 `frontend/src/components/TierTable.tsx`: static 8-tier official-rules reference table (+40).
- [ ] 8.3 `frontend/src/pages/MyNumbers.tsx` (+235): single CTA with busy-hold, indeterminate in-flight indicator, StageReport list, TicketCards reusing `CombinationRow` columns (`super_number`/`score` survive from Generator.tsx:27–44), dual-draw label, persistent disclaimer, `ErrorState` retry via `useApi`.
- [ ] 8.4 Route/nav swap (dl-frontend-page precedent): `App.tsx` route `/generator`→`/my-numbers`; `Sidebar.tsx` nav entry; update `App.test.tsx` + `Sidebar.test.tsx` assertions.
- [ ] 8.5 Delete `frontend/src/pages/Generator.tsx` + `Generator.test.tsx` in the same commit as 8.4.

**Commits**: `feat(numbers-ui): add pipeline types and runNumbersPipeline client` (8.1) → `feat(numbers-ui): add MyNumbers pipeline page with prize tiers` (7.1–7.7, 8.2–8.3) → `refactor(numbers-ui): replace generator route with my-numbers` (8.4–8.5).

### Phase 9: Regression gates

- [ ] 9.1 Full frontend suite: `cd frontend && npx vitest run`
- [ ] 9.2 tsc/build gate: `cd frontend && npm run build`
- [ ] 9.3 Lint/format: `cd frontend && npm run lint && npx prettier --check "src/**/*.{ts,tsx,css}"`

## Implementation Order

S1 → S2 → S3 (stacked-to-main). S2 consumes S1's scored GenerationResult; S3 consumes S2's endpoint contract. Each slice is independently revertable; goldens travel atomically with the version bump.
