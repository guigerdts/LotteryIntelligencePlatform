# Proposal: Numbers Pipeline — Gen-Only Chain

## Intent

The `/numbers` endpoint runs 8 stages but only 3 produce consumed output. `ml/dl/bt/rank/select` add minutes-scale latency while `gen` reads only probability snapshot + stats. The frontend mirrors 8 stages, contradicting reality. This removes the dead meta chain and makes `gen` self-sufficient.

## Scope

### In Scope
- Reduce backend `STAGE_ORDER` to `(stats, features, gen)`
- Remove dead stages, `_DEPS`, `_GATED_STAGES`, adapter classes, helper functions
- Decouple `gen` from requiring an active `MetaSelection` (deterministic seed fallback)
- Align frontend `PipelineStageName` and test assertions to 3 stages
- Update API docstring in `pipeline.py`

### Out of Scope
- Backtesting engine (`api/v1/bt.py`) — independent, untouched
- Probability/feature engine logic — unchanged
- `generator-output` spec requirements — unaffected

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `numbers-orchestrator`: REQ-01 chain reduces to 3 stages; REQ-02 prerequisite detection reduces; REQ-03 report reduces to 3 entries; bt-before-rank scenario removed.

## Approach

1. **Backend**: Rewrite `STAGE_ORDER`, remove `_DEPS`/`_GATED_STAGES`/adapters/dead helpers. In `_resolve_selection`, return seed object with `fingerprint = hash(prob_snapshot_fingerprint, lottery_id)` when no active `MetaSelection` exists.
2. **Frontend**: `PipelineStageName` → `"stats"|"features"|"gen"`. Fix test assertions.
3. **Tests**: Rewrite 5 backend test files asserting 8-stage behavior.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/backend/app/services/pipeline_service.py` | Modified | `STAGE_ORDER`, remove dead stages/helpers |
| `backend/src/backend/app/services/gen_service.py` | Modified | Seed fallback in `_resolve_selection` |
| `frontend/src/types/pipeline.ts` | Modified | `PipelineStageName` → 3 values |
| `frontend/src/pages/MisNumeros.test.tsx` | Modified | Stage count + R2 assertions |
| `backend/src/backend/app/api/v1/pipeline.py` | Modified | Docstring |
| `backend/tests/pipeline/` (5 files) | Modified | 8-stage → 3-stage assertions |
| `openspec/specs/numbers-orchestrator/spec.md` | Modified | Delta for REQ-01/02/03 |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Test rewrites miss edge cases | Medium | Full suite pass required |
| Fresh-DB output differs (no selection) | High | Intended: deterministic from prob snapshot + lottery_id |
| Removing adapters breaks imports | Low | Confirmed internal to pipeline_service |

## Rollback Plan

Revert `STAGE_ORDER` to 8-tuple, restore `_DEPS`/`_GATED_STAGES`/adapters. No data migration. Frontend revert restores 8-stage types.

## Dependencies
None — self-contained.

## Success Criteria

- [ ] Pipeline runs exactly 3 stages: `stats`, `features`, `gen`
- [ ] `gen` succeeds without an active `MetaSelection`
- [ ] Frontend `STAGE_ORDER` matches backend
- [ ] All backend and frontend tests pass

## Proposal Assumptions

- Option 1 chosen (backend chain reduction + gen decoupling)
- Seed fallback: `hash(prob_snapshot_fingerprint, lottery_id)` + `GENERATOR_VERSION`; `selection.id` → `0`
- Backtesting independent, untouched
- `features` stage logic unchanged
- `generator-output` specs unaffected
- ~5 backend test files need rewriting
