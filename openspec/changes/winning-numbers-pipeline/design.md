# Design: Winning Numbers Pipeline (Baloto/Revancha)

## Technical Approach

Three independently shippable slices on code-verified seams: **S1** completes generator output (SB + score) at the existing `sampling.py`/`gen_service.py:167` seams; **S2** adds a new orchestrator service+endpoint wrapping the already-idempotent stage services (no internals refactored); **S3** swaps the raw Generator form for a pipeline-driven page mirroring `Models.tsx` structure. Specs: `generator-output`, `numbers-orchestrator`, `mis-numeros-page`.

## Architecture Decisions

| # | Decision | Choice | Alternatives rejected | Rationale |
|---|----------|--------|----------------------|-----------|
| D1 | SB stream position | Draw SB with the SAME `isolated_rng(seed)` instance (`sampling.py:62`), once per **accepted** combo, after numbers validation passes | Separate RNG; SB before numbers | One seed reproduces numbers+SB byte-for-byte; post-acceptance draw keeps stream consumption independent of rejection counts |
| D2 | SB marginal source | Empirical frequencies over imported `SuperNumber.value`; **uniform 1–16** when sparse (<32 observations); `GEN_NO_HISTORY` (422) when zero draws | Always uniform; Bayesian shrinkage | Spec-mandated fallbacks; simple, deterministic |
| D3 | Score formula | `score = entry_score × mean(P(n) for n∈numbers)` rounded to 6 dp; computed in `gen_service.generate()` where pools carry both inputs | Geometric mean; rank-based proxy | Finite>0 guaranteed (F5 probs and selection scores are >0); uses exactly "entry-selection weight × probability distribution" per R3 |
| D4 | Score-null fallback | **None — score is required, never null** | Allow null when no `selection_id` passed | Dead path: `_resolve_selection` (gen_service.py:268–301) raises `GEN_NO_SELECTION` whenever no explicit or active selection exists; generation *cannot* run selection-less, so R3's non-null mandate is always satisfiable |
| D5 | Legality tightening | `validate_combination(numbers, sb, cfg)` returns `False` when `sb is None` (currently skips check); gate pre-persist in sampling loop + service assert before `create_active_snapshot` | Separate strict validator | Only caller is the sampling loop (verified blast radius); legacy reads never invoke it → unaffected |
| D6 | Version bump | `GENERATOR_VERSION` `"1.0.0"`→`"2.0.0"` (feeds `generation_seed`/`snapshot_fingerprint`, identity.py:35/65); regenerate goldens in same commit + aliasing-guard test (no new fingerprint equals any pre-change fixture) | Minor bump; no bump | Stream-consumption change alters outputs; major bump signals breaking output identity |
| D7 | Orchestrator placement | New `services/pipeline_service.py` + `api/v1/pipeline.py`; calls existing services in order; **zero changes to stage-service internals** | Refactor meta_service; job+polling | All stage entries are fingerprint-idempotent already; sync-with-stages fits minutes-scale local runs (proposal approach ratified) |
| D8 | bt-before-rank | **Detect-and-rerank**: derive ctx post-bt via `resolve_context_vector(lottery,"backtesting")` + `compute_context_hash` (same primitives rank uses internally); rerun rank when no active ranking for ctx **or** `ranking.created_at <= latest_active_BtSnapshot.created_at`; pass ctx explicitly to `select(context_hash=…)` — param already exists (meta_service.py:224) | Hardcode-free refactor of meta internals; timestamp-only check | Retires the `meta_service.py:242` hardcoded `"backtesting"` coupling without touching META logic; one repair attempt, else `PIPE_STAGE_FAILED(rank)` (prevents rerun loops if derivations diverge) |
| D9 | Probability ownership | Canonical stage `features` runs `FeatureEngineService.generate` **then** `ProbabilityService.generate` (spec fixes 8 stages; gen's `_load_distribution` needs an active prob snapshot) | 9th stage; lazy heal inside gen | Keeps the spec's canonical eight; both services share stats-prereq and fingerprint idempotency |
| D10 | HTTP codes (ratified a) | `GEN_INVALID_NUMBERS`/`GEN_INVALID_SUPER_NUMBER`→422; `GEN_NO_HISTORY`→422; `PIPE_STAGE_FAILED`→502 | 400/500 variants | 422 matches `GEN_COUNT_INVALID`/`INSUFFICIENT_DATA` precedents in `_CODE_TO_STATUS`; stage failure is an upstream-chain fault behind a valid request → 502-family, distinct from unhandled-crash 500 |
| D11 | Counts (ratified b) | `DEFAULT_COUNT=10` stays backend-side (GEN-002 contract); page sends `count: 5` | Change backend default | Product decision lives in the UI layer; CLI/API semantics untouched |
| D12 | ml/dl auto-train | Missing/stale → `MlService.train`/`DlService.train` with registry defaults (`model_set="core"`, DL order `mlp→lstm`) | Fail-and-instruct | Owner-ratified minutes-scale latency; training is fingerprint-idempotent |

## Data Flow

```
POST /pipeline/numbers {lottery_id,count?,seed?}
  └→ PipelineService.run ─┬ stats → features(+prob) → ml → dl → bt    (data prep)
                          ├ rank → select(ctx_hash=bt-derived)        (meta)
                          └ gen(count,seed) → snapshot_id             (output)
  each stage: prereq check → [skip | repair-run] → {name,status,detail}
  failure → PIPE_STAGE_FAILED(stage), later stages skipped, artifacts persist
```

## File Changes

### S1 ≈430 LOC
| File | Action | Δ est |
|------|--------|-------|
| `backend/src/backend/app/generators/sampling.py` | Modify — `(combo, sb)` return, SB marginal param, D1/D5 | +45/−12 |
| `backend/src/backend/app/generators/validation.py` | Modify — D5 | +6/−4 |
| `backend/src/backend/app/services/gen_service.py` | Modify — `_load_sb_marginal`, D3 score, persist sb+score @:167, `GEN_NO_HISTORY` | +60/−8 |
| `backend/src/backend/app/generators/version.py` | Modify — D6 | =1 |
| `backend/src/backend/app/services/errors.py` | Modify — 3 codes | +9 |
| `backend/src/backend/app/api/errors.py` | Modify — status rows | +3 |
| `backend/src/backend/app/schemas/gen.py` | Verify non-null typing of `super_number`/`score` echo | ±4 |
| `backend/tests/gen/**` (sampling, generate, types@:98 version assert, goldens regenerated) | Mod/New | +300 |

### S2 ≈330 LOC
| File | Action | Δ est |
|------|--------|-------|
| `backend/src/backend/app/services/pipeline_service.py` | Create — stage runner, healing matrix, D8 | +175 |
| `backend/src/backend/app/schemas/pipeline.py` | Create — request/response models | +45 |
| `backend/src/backend/app/api/v1/pipeline.py` | Create — one endpoint | +55 |
| `backend/src/backend/app/api/v1/router.py` | Modify — mount | +2 |
| `backend/src/backend/app/api/errors.py` + `services/errors.py` | Modify — `PIPE_STAGE_FAILED` | +10 |
| `backend/tests/pipeline/**` | New | +280 |

### S3 ≈390 LOC
| File | Action | Δ est |
|------|--------|-------|
| `frontend/src/pages/MyNumbers.tsx` | Create — CTA, busy-hold, StageReport, TicketCards, disclaimer | +235 |
| `frontend/src/components/TierTable.tsx` | Create — static 8 tiers | +40 |
| `frontend/src/services/gen.ts` / `types/gen.ts` | Modify — `runNumbersPipeline`, stage/result types | +32 |
| `frontend/src/App.tsx` | Modify — route swap `/my-numbers`, nav label | ±8 |
| `frontend/src/pages/Generator.tsx` | Delete (rollback = revert PR) | −235 |
| `frontend/src/pages/MyNumbers.test.tsx` | Create — MSW, 8 scenarios | +260 |

## Interfaces / Contracts

```python
# POST /api/v1/pipeline/numbers  (SuccessEnvelope)
PipelineRunRequest(lottery_id: int, count: int|None=None, seed: int|None=None)
PipelineStageResult(name: str, status: Literal["skipped","completed","failed"],
                    snapshot_id: int|None, fingerprint: str|None,
                    error_code: str|None, detail: str)
PipelineRunResult(stages: list[PipelineStageResult],  # 8, canonical order
                  result: GenerationResult|None)       # null on failure
```

Skipped-vs-completed detected by comparing active-artifact fingerprint before/after each service call. Frontend reuses `useApi` + `ErrorState` retry; `CombinationRow` already renders `super_number`/`score` (Generator.tsx:27–44 columns survive into MyNumbers).

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit (pytest) | SB in-range/reproducible; uniform fallback; `GEN_NO_HISTORY`; validate None-SB False; score finite/non-null; version-bump aliasing guard | Extend `tests/gen/`, seeded fixtures |
| Integration (pytest) | Cold chain 8×completed; partial heal skips upstream; fresh-draw invalidates downstream only; double-run zero new versions; stage-failure aborts before gen; rerank-on-staleness | `tests/pipeline/` against service layer |
| E2E (vitest+MSW) | 8 scenarios: single-request-per-CTA; busy-hold+retry-on-500; ordered 8-stage report; failed-stage-without-crash; dual-draw label & no toggle; payload count=5; 8-tier table; disclaimer persists idle+post-gen | `MyNumbers.test.tsx`, Models-page patterns |

## Threat Matrix

N/A — no routing/shell/subprocess/VCS-PR/executable-classification/process-integration boundary; the only new surface is one internal FastAPI route behind the existing envelope/error handlers.

## Migration / Rollout

No DB migrations (`super_number` stays nullable; legacy rows readable). Forward-only output-identity change via D6. Per-slice rollback: revert that slice's PR (S2 endpoint additive; S3 restores Generator).

## Open Questions

None blocking — D4, D10–D12 resolve the spec-flagged decisions.
