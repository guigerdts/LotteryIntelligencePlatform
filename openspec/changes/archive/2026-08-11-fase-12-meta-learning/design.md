# Design: F12 — Meta Learning

## Technical Approach

F12 adds a deterministic model-ranking layer that consumes persisted engine outputs (F7/F8/F9/F10) and produces ranked selections for F13. It follows the established snapshot lifecycle (atomic upsert, monotonic version, SHA-256 fingerprint) for `meta_*` tables. Scoring uses weighted-sum normalization (no learned meta-model). Context resolution derives from existing DB columns only. All operations are read-only to `exp_*` and engine tables — F12 never executes engines or generates numbers.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| **Scoring algorithm** | Weighted sum | Learned meta-model, percentile ranking | Transparent, deterministic, interpretable; no pandas (NFR-META-07) |
| **Normalization** | Per-engine min-max | Global min-max, z-score | Fair cross-engine comparison; z-score needs global stats |
| **Context hash** | SHA-256(lottery_id, draws_from, draws_to, cut, window, engine_type) | Broader context | Minimal, data-driven; all vars exist in current schema (META-03) |
| **Snapshot pattern** | Same as F7-F11 (active/retired/failed) | Soft-delete, version table | Proven across 6 engines; audit trail; idempotency |
| **Failed run handling** | Exclude entirely (not scored) | Score as 0.0 | Failed = execution error, not performance; penalizing biases toward "never tried" |
| **Engine metric reading** | Reuse `_read_*_metrics` pattern from ExpService | Centralized metric registry | Follows existing pattern; avoids new abstraction layer |
| **Weight override** | Per-lottery via config_json | Global config only | META-019 requires per-lottery flexibility |

## Data Model

### Migration 0014

**`meta_rankings`**: `id` PK, `lottery_id` FK→lottery RESTRICT, `context_hash` String(64), `version` String(32), `status` String(16) CHECK `active|retired|failed`, `fingerprint` String(64), `config_json` Text nullable, `created_at` DateTime(tz). Unique `(lottery_id, context_hash, fingerprint)`. Index `ix_meta_rankings_lottery_context` on `(lottery_id, context_hash)`.

**`meta_ranking_entries`**: `id` PK, `ranking_id` FK→meta_rankings RESTRICT, `model_id` String(100), `engine_type` String(20) CHECK `backtesting|ml|dl|optimization`, `score` Float, `metrics_json` Text, `created_at` DateTime(tz). Index `ix_meta_ranking_entries_ranking` on `(ranking_id)`.

**`meta_selections`**: `id` PK, `lottery_id` FK→lottery RESTRICT, `context_hash` String(64), `version` String(32), `status` String(16) CHECK `active|retired|failed`, `fingerprint` String(64), `config_json` Text nullable, `created_at` DateTime(tz). Unique `(lottery_id, context_hash, fingerprint)`. Index `ix_meta_selections_lottery_context` on `(lottery_id, context_hash)`.

**`meta_selection_entries`**: `id` PK, `selection_id` FK→meta_selections RESTRICT, `ranking_id` FK→meta_rankings RESTRICT, `model_id` String(100), `engine_type` String(20) CHECK `backtesting|ml|dl|optimization`, `rank` Integer, `score` Float, `created_at` DateTime(tz). Index `ix_meta_selection_entries_selection` on `(selection_id)`.

**Downgrade**: DROP `meta_selection_entries`, `meta_selections`, `meta_ranking_entries`, `meta_rankings` in order.

## Module Structure

```
backend/src/backend/app/meta/
├── __init__.py              # Package seam (docstring only)
├── types.py                 # ContextVector, NormalizedMetrics, RankingData, SelectionData, WeightConfig
├── context.py               # resolve_context_vector(), compute_context_hash()
├── normalization.py         # normalize_per_engine(), COMMON_METRICS, ENGINE_EXCLUDED
├── scoring.py               # compute_score(), DEFAULT_WEIGHTS, validate_weights()
├── ranking.py               # build_ranking_entries(), compute_fingerprint()
├── selection.py             # select_top_k()
├── snapshot_store.py        # MetaSnapshotStore — meta_* I/O owner (lifecycle pattern)
└── version.py               # META_LEARNING_VERSION constant

backend/src/backend/app/models/
├── meta_ranking.py          # MetaRanking ORM model
├── meta_ranking_entry.py    # MetaRankingEntry ORM model
├── meta_selection.py        # MetaSelection ORM model
└── meta_selection_entry.py  # MetaSelectionEntry ORM model

backend/src/backend/app/services/
├── meta_service.py          # MetaService — composition root (rank, get_ranking, select, get_selection)

backend/src/backend/app/api/v1/
├── meta.py                  # API router (4 endpoints)

backend/src/backend/app/schemas/
├── meta.py                  # Pydantic v2 schemas (request/response)

backend/alembic/versions/
├── 0014_meta_tables.py      # Migration (META-015)

backend/tests/meta/
├── __init__.py
├── test_types.py
├── test_context.py
├── test_normalization.py
├── test_scoring.py
├── test_ranking.py
├── test_selection.py
├── test_snapshot_store.py
├── test_meta_service.py
├── test_meta_api.py
└── test_meta_cli.py
```

## Domain Types

```python
@dataclass(frozen=True)
class ContextVector:
    lottery_id: int
    draws_from: int       # draw number
    draws_to: int         # draw number (temporal boundary)
    cut: int | None       # ML/DL walk-forward cut
    window: int | None    # DL sequence length
    engine_type: str      # backtesting|ml|dl|optimization

@dataclass(frozen=True)
class WeightConfig:
    hit_rate: float = 0.3
    average_matches: float = 0.3
    consistency_score: float = 0.2
    precision: float = 0.1
    recall: float = 0.1

    def validate(self) -> None: ...  # sum != 0

@dataclass(frozen=True)
class RankingEntry:
    model_id: str
    engine_type: str
    score: float
    metrics: dict[str, float]

@dataclass(frozen=True)
class SelectionEntry:
    model_id: str
    engine_type: str
    rank: int
    score: float
```

## Context Resolution

**Sources**: lottery_id (request), draws_from/draws_to from engine snapshots, cut from ml_snapshots/dl_snapshots, window from dl_snapshots, engine_type from request.

**Context hash** = `SHA-256(json.dumps({"lottery_id": L, "draws_from": F, "draws_to": T, "cut": C, "window": W, "engine_type": E}, sort_keys=True))`.

**Isolation**: Context always scoped per lottery_id. No cross-lottery contamination (META-012).

**Temporal bound**: draws_to included in hash; ranking only considers snapshots with draws_to ≤ selection point (META-011).

## Cross-Engine Normalization

**Common metrics** (cross-engine comparable): `hit_rate`, `average_matches`, `consistency_score`, `precision`, `recall`, `f1_score`.

**Engine-excluded**: `best_fitness` (OPT-specific), `total_draws_evaluated` (context only).

**Per-engine min-max**: Within each engine_type, `(value - min) / (max - min)`. Constant values → 0.0. Missing metrics → 0.0 (conservative).

**consistency_score inversion**: Lower is better in raw form → invert before scoring so higher = better for weighted sum.

**Metric reading**: Reuse pattern from `ExpService._read_*_metrics()` — lazy import engine models, parse JSON columns.

## Scoring

**Formula**: `score = Σ(normalized_metric × weight)` for metrics present in both the snapshot and weight config.

**Default weights**: hit_rate=0.3, average_matches=0.3, consistency_score=0.2, precision=0.1, recall=0.1.

**Per-lottery override**: `config_json` on `meta_rankings` contains `{"weights": {...}}`. Full replacement, no partial merge.

**Validation**: Weights must sum ≠ 0. Invalid → META_WEIGHTS_INVALID (422).

**Invalid candidates**: Snapshots with missing all common metrics get score 0.0 (not excluded, conservatively ranked last).

## Ranking

**Sort**: `np.argsort(kind='stable')` on composite scores, descending (NFR-META-10).

**Tie-breaking**: Stable sort preserves insertion order for equal scores. Deterministic given same input order.

**Fingerprint**: `SHA-256(json.dumps({"lottery_id": L, "context_hash": H, "entries": [{"model_id": M, "score": S}...]}, sort_keys=True))`.

**Versioning**: Monotonic per (lottery_id, context_hash): `version = max(version) + 1`.

**Lifecycle**: New ranking → `active`. Supersedes old → old `retired`, new `active`. Atomic single-transaction write.

**Idempotency**: Same fingerprint → return existing active, no new rows (META-007).

## Selection

**Strategy**: Top-K from ranking where score ≥ min_score.

**Defaults**: top_k=5 (min=1, max=20), min_score=0.0. Per-lottery configurable via request params (META-020).

**Insufficient qualifying**: Return fewer than K if threshold filters out candidates.

**Fingerprint**: `SHA-256(json.dumps({"lottery_id": L, "context_hash": H, "ranking_fingerprint": RF, "top_k": K, "min_score": S}))`.

**Lifecycle**: Same pattern as ranking — active/retired/failed, atomic write, monotonic version.

## History / Comparison

All ranking and selection snapshots retained (active + retired). Queryable by (lottery_id, context_hash, status). Comparing versions: query by lottery_id + context_hash, order by version DESC, compare entries.

## API Endpoints (4)

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | `/meta/rank` | `{lottery_id, engine_types?, weights?, draws_to?}` | `RankingResult` | 404 META_NO_ENGINE_DATA, 422 META_WEIGHTS_INVALID |
| GET | `/meta/ranking` | `?lottery_id&context_hash?` | `RankingSnapshot` | 404 META_RANKING_NOT_FOUND |
| POST | `/meta/select` | `{lottery_id, top_k?, min_score?}` | `SelectionResult` | 404, 422 META_TOP_K_INVALID |
| GET | `/meta/selection` | `?lottery_id&context_hash?` | `SelectionSnapshot` | 404 META_SELECTION_NOT_FOUND |

All use standard envelope `{success, data|error, timestamp}`.

## CLI Commands (4)

| Command | Arguments | Output |
|---------|-----------|--------|
| `lip meta rank` | `--lottery-id`, `[--engine-types]`, `[--weights]` | JSON ranking |
| `lip meta ranking` | `--lottery-id`, `[--context-hash]` | JSON ranking snapshot |
| `lip meta select` | `--lottery-id`, `[--top-k]`, `[--min-score]` | JSON selection |
| `lip meta selection` | `--lottery-id`, `[--context-hash]` | JSON selection snapshot |

## Error System

| Error Class | Code | HTTP | When |
|-------------|------|------|------|
| `MetaServiceError` | `META_RANKING_NOT_FOUND` | 404 | Invalid lottery_id or context_hash for ranking |
| `MetaServiceError` | `META_SELECTION_NOT_FOUND` | 404 | Invalid lottery_id or context_hash for selection |
| `MetaServiceError` | `META_NO_ENGINE_DATA` | 404 | No engine snapshots found for lottery |
| `MetaServiceError` | `META_WEIGHTS_INVALID` | 422 | Weights sum to zero or invalid format |
| `MetaServiceError` | `META_TOP_K_INVALID` | 422 | top_k < 1 or > 20 |
| `MetaServiceError` | `META_DUPLICATE_RANKING` | 409 | Same fingerprint, active ranking exists |

All subclass `ServiceError` (NFR-META-09).

## Sequence Diagrams

### Context Resolution → Ranking
```
API/CLI → MetaService.rank(lottery_id, weights)
  → resolve_context_vector(lottery_id) → ContextVector
  → compute_context_hash(vector) → "abc123..."
  → Read engine snapshots (bt_*, ml_*, dl_*, opt_*) WHERE draws_to ≤ now
  → Filter status != 'failed' (META-04)
  → normalize_per_engine(snapshots) → normalized metrics
  → compute_score(normalized, weights) → score per snapshot
  → build_ranking_entries(scored) → sorted entries
  → compute_fingerprint(lottery_id, context_hash, entries) → fp
  → MetaSnapshotStore.find_by_fingerprint(fp) → check idempotency
  → MetaSnapshotStore.create_active_ranking(...) → atomic write
  ← RankingResult
```

### Selection
```
API/CLI → MetaService.select(lottery_id, top_k, min_score)
  → Get active ranking for lottery_id (or compute if not exists)
  → select_top_k(ranking.entries, top_k, min_score) → selected
  → compute_selection_fingerprint(ranking_fp, top_k, min_score) → fp
  → MetaSnapshotStore.find_by_fingerprint(fp) → idempotency
  → MetaSnapshotStore.create_active_selection(...) → atomic write
  ← SelectionResult
```

### History Retrieval
```
API/CLI → MetaService.get_ranking(lottery_id, context_hash?)
  → MetaSnapshotStore.get_rankings(lottery_id, context_hash)
  → Return all (active + retired) ordered by version DESC
  ← RankingSnapshot
```

## Boundary Enforcement

**F12 DOES**: Read engine metric tables, compute scores, produce ranking/selection snapshots.

**F12 DOES NOT**:
- Execute backtests (F10)
- Train ML/DL models (F7/F8)
- Run optimization (F9)
- Register/manage experiments (F11)
- Generate number combinations (F13)
- Implement dashboard/UI (F14)
- Write to `exp_*` tables (read-only)
- Import engine modules at module level (lazy imports only)

## Technical Risks

| Risk | Mitigation |
|------|------------|
| Leakage from future data | draws_to ≤ selection point enforced; context_hash includes draws_to |
| Overfitting to historical | Uses out-of-sample metrics from engine snapshots only |
| Survivorship bias | Failed runs excluded from scoring (not penalized); all active models included |
| Scale differences between engines | Per-engine min-max normalization before cross-engine comparison |
| Score tie-breaking | Stable sort preserves insertion order; deterministic given same input |
| Context drift | Context hash changes with any variable change; old rankings remain valid for old contexts |
| Determinism | No stochastic elements; stable sort; SHA-256 fingerprint |
| Idempotency | Same fingerprint returns existing; no duplicate rows |

## Performance

NFR: Ranking computation ≤ 500ms p95 for ≤ 1000 model snapshots. Single-table queries with index lookup. Normalization is O(n) per engine. Sorting is O(n log n). All within budget for SQLite at this scale.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No data migration. Migration 0014 is purely additive (4 new tables). Rollback: `alembic downgrade -1` drops the 4 tables. All changes are additive; no existing table modified.

## Traceability: Design → Requirements

| Design Area | Requirements |
|-------------|--------------|
| Module structure | META-015, META-018 |
| Context resolution | META-003, META-011, META-012 |
| Normalization | META-002 |
| Scoring | META-001, META-019 |
| Ranking | META-005, META-007, META-008, META-009, META-010 |
| Selection | META-006, META-020 |
| API | META-013 |
| CLI | META-014 |
| Errors | META-016 |
| Lifecycle | META-008 |
| Failed runs | META-004 |
| Freshness | META-017 (ignored in MVP) |

## Open Questions

- [ ] None — all design decisions resolved per spec and proposal.

---

**Ready for tasks (sdd-tasks) upon confirmation.**
