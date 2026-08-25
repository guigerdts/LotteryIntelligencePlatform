# Design: Numbers Pipeline — Gen-Only Chain

## Technical Approach

Reduce the backend pipeline from 8 stages to 3 (`stats → features → gen`), removing the dead `ml/dl/bt/rank/select` chain. Decouple `gen` from requiring an active `MetaSelection` by introducing a deterministic seed fallback. Align frontend types and tests to match the new 3-stage contract.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Stage reduction | Delete 5 stage branches + helpers | Keep stubs/marks | Dead code adds confusion; full removal is safer |
| `_DEPS`/`_GATED_STAGES` | Remove entirely | Keep empty dicts | No gated stages remain after removing `ml`/`bt`; empty containers are noise |
| `_gated_skip` | Remove method | Keep as always-false | Simpler — the `run()` loop no longer needs the gate check |
| `_RunState.context_hash` | Remove field | Keep as always-None | No stage consumes it; dead state is confusing |
| Selection fallback | `selection_id=0` + `fingerprint=hash(prob_checksum, lottery_id)` | Raise error / skip gen | `gen` must be self-sufficient per REQ-01 scenario; `id=0` scopes GenSnapshotStore safely |
| Adaptation classes | Delete all 4 (`_MlDrawAdapter`, `_MlFeatureAdapter`, `_DlDrawAdapter`, `_DlFeatureAdapter`) | Keep unused | Internal to pipeline_service only; no external consumers |

## Data Flow

```
stats ──→ features ──→ gen
  │           │          │
  │           │          └─ ProbSnapshot.checksum + lottery_id → fallback fingerprint
  │           └── FeatureSnapshot + ProbSnapshot (active)
  └── StatSnapshot (active)
```

`gen` reads the active `ProbSnapshot` (already loaded by `_load_distribution`) and derives a deterministic fingerprint from `ProbSnapshot.checksum` + `lottery_id` when no `MetaSelection` exists.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/backend/app/services/pipeline_service.py` | Modify | Rewrite `STAGE_ORDER`, `run()`, `_execute_stage`, `_read_artifact`; delete `_DEPS`, `_GATED_STAGES`, `_gated_skip`, `_safe_context_hash`, `derive_context_hash`, `_run_rank`, `_ranking_stale`, `_naive`, 4 adapter classes, `_RunState.context_hash` |
| `backend/src/backend/app/services/gen_service.py` | Modify | Fallback in `_resolve_selection`: build lightweight selection-like object with `id=0`, `fingerprint=hash(prob_snapshot.checksum, lottery_id)` |
| `frontend/src/types/pipeline.ts` | Modify | `PipelineStageName` → `"stats" \| "features" \| "gen"`; `STAGE_ORDER` → 3 values |
| `frontend/src/pages/MisNumeros.test.tsx` | Modify | `STAGE_ORDER` → 3 entries; 8→3 stage assertions; remove `failedRankStages` fixture |
| `backend/src/backend/app/api/v1/pipeline.py` | Modify | Docstring: 3-stage chain |
| `backend/tests/pipeline/conftest.py` | Modify | `STAGE_ORDER` → 3; trim `stage_recorder` targets; simplify `clear_stages`; remove `fast_dl_training`/`fast_ml_training` |
| `backend/tests/pipeline/test_pipeline_cold_chain.py` | Modify | 3-stage assertions; remove bt-before-rank ordering check |
| `backend/tests/pipeline/test_pipeline_healing.py` | Modify | New 3-row healing matrix (`ALL` = 3 stages); remove `fast_dl_training` dependency |
| `backend/tests/pipeline/test_pipeline_idempotent.py` | Modify | Same structure, 3 stages |
| `backend/tests/pipeline/test_pipeline_failures.py` | Modify | Replace `fail_rank` with `fail_features`; assert `features` failure aborts before `gen` |
| `backend/tests/pipeline/test_pipeline_context.py` | Delete | Tests D8 bt-before-rank context derivation; no longer applicable |
| `backend/tests/pipeline/test_pipeline_autotrain.py` | Delete | Tests ml/dl auto-train gating; no longer applicable |

## Interfaces / Contracts

### `pipeline_service.py` simplified structure

```python
STAGE_ORDER: tuple[str, ...] = ("stats", "features", "gen")
# _DEPS, _GATED_STAGES, _gated_skip — REMOVED (no gated stages)
# _RunState.context_hash — REMOVED
# derive_context_hash, _safe_context_hash, _run_rank, _ranking_stale, _naive — REMOVED
# _MlDrawAdapter, _MlFeatureAdapter, _DlDrawAdapter, _DlFeatureAdapter — REMOVED
```

### `gen_service._resolve_selection` fallback

```python
def _resolve_selection(self, lottery_id, selection_id):
    # ... existing explicit-override path unchanged ...
    # Active selection lookup ...
    if selection is None:
        # Fallback: build lightweight selection-like object (no MetaSelection needed)
        from backend.app.models.prob_snapshot import ProbSnapshot
        stmt = (
            select(ProbSnapshot)
            .where(ProbSnapshot.lottery_id == lottery_id, ProbSnapshot.status == "active")
            .order_by(ProbSnapshot.version.desc())
            .limit(1)
        )
        prob = self._session.execute(stmt).scalar_one_or_none()
        if prob is None:
            raise GenServiceError(GEN_NO_DISTRIBUTION, ...)
        fp = hashlib.sha256(
            _canonical_json({"checksum": prob.checksum, "lottery_id": lottery_id}).encode()
        ).hexdigest()
        return types.SimpleNamespace(id=0, fingerprint=fp)
    return selection
```

**Determinism**: `ProbSnapshot.checksum` is a stable SHA-256 of the probability output; same inputs → same checksum → same fallback fingerprint → same `generation_seed` → same snapshot (GEN-008 idempotency preserved).

**`selection_id=0` safety**: `GenSnapshotStore.find_by_fingerprint` queries by `fingerprint` alone (no `selection_id` filter). `next_version(lottery_id, 0)` scopes versioning to `selection_id=0` only — no collision with real-selection snapshots.

### Frontend types

```typescript
export type PipelineStageName = "stats" | "features" | "gen";
// STAGE_ORDER = ["stats", "features", "gen"] in test file
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_resolve_selection` fallback determinism | Same `prob.checksum` + `lottery_id` → same `fingerprint`; different checksum → different fingerprint |
| Unit | `selection_id=0` isolation | `GenSnapshotStore` with `selection_id=0` doesn't interfere with `selection_id=5` snapshots |
| Integration | Cold chain runs 3 stages in order | Rewrite `test_pipeline_cold_chain.py`: assert `names == ["stats", "features", "gen"]` |
| Integration | Healing matrix with 3 stages | Rewrite `test_pipeline_healing.py`: new `HEALING_ROWS` with 3-stage `ALL` set |
| Integration | Gen succeeds without MetaSelection | New test: run pipeline on fresh DB (no MetaSelection rows), assert `gen` completes |
| Integration | Stage failure aborts cleanly | Rewrite `test_pipeline_failures.py`: monkeypatch `FeatureEngineService.generate` to raise, assert `features` failure, `gen` never runs |
| Frontend | 3-stage type + test assertions | Update `MisNumeros.test.tsx`: 3 stages in `STAGE_ORDER`, `toHaveLength(3)`, remove `failedRankStages` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No data migration required. Existing `GenSnapshot` rows with real `selection_id` values remain valid. New snapshots with `selection_id=0` coexist safely. No feature flags needed — the change is a clean cut.

## Open Questions

None — all decisions are resolved by the codebase analysis.
