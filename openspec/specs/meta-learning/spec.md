# Spec — Meta Learning (`meta-learning`)

**Change**: `fase-12-meta-learning` · **Store**: `openspec` · **Date**: 2026-08-11
**Artifact**: spec (this change) — new capability `meta-learning`, parallel to `backtesting-engine` (F10), `experiment-engine` (F11).

## Purpose

Evaluate, rank, and select the best-performing models across engines (ML/DL/OPT/BT) per lottery context. Consumes persisted engine outputs, produces deterministic ranked selections for F13 consumption. Weighted deterministic scoring (MVP); no learned meta-model.

## Requirements Overview

| ID | Requirement | Priority |
|----|-------------|----------|
| META-001 | Weighted scoring — configurable weights, per-engine metric extraction | P0 |
| META-002 | Cross-engine normalization — per-engine min-max, common metrics only | P0 |
| META-003 | Context resolution — context vector from existing DB columns, SHA-256 hash | P0 |
| META-004 | Failed run exclusion — status=failed snapshots excluded from scoring | P0 |
| META-005 | Ranking — immutable snapshot, stable sort, monotonic version | P0 |
| META-006 | Selection — top-K + threshold, bounded output for F13 | P0 |
| META-007 | Idempotency — same fingerprint returns existing ranking/selection | P0 |
| META-008 | Lifecycle — active\|retired\|failed transitions, atomic writes | P0 |
| META-009 | Fingerprint — SHA-256 over (lottery_id, context_hash, ranking_data) | P0 |
| META-010 | History — all snapshots retained, version per (lottery_id, context_hash) | P0 |
| META-011 | Leakage prevention — draws_to ≤ selection point, no future data | P0 |
| META-012 | lottery_id isolation — no cross-lottery contamination | P0 |
| META-013 | API — 4 endpoints (rank, ranking, select, selection) | P0 |
| META-014 | CLI — 4 commands (rank, ranking, select, selection) | P0 |
| META-015 | Persistence — 4 tables (meta_rankings, meta_ranking_entries, meta_selections, meta_selection_entries) | P0 |
| META-016 | Error taxonomy — MetaServiceError subclass ServiceError | P0 |
| META-017 | Freshness extension point — config_json field ignored in MVP | P1 |
| META-018 | Boundary F11/F12/F13 — read-only to exp_*, no engine execution, no generation | P0 |
| META-019 | Weight configuration — global defaults overridable per-lottery via config_json | P0 |
| META-020 | Top-K defaults — default 5, min 1, max 20, per-lottery configurable | P0 |

## Requirements

### META-001: Weighted Scoring

The system SHALL compute a composite score per model snapshot using a weighted sum of normalized metrics. Default weights: `hit_rate=0.3, average_matches=0.3, consistency_score=0.2, precision=0.1, recall=0.1`. Weights MUST be configurable per-lottery via `config_json` on `meta_rankings`. Weights MUST NOT sum to zero.

**Entities touched**: `meta_rankings.config_json`, engine metric snapshots (read-only)

#### Scenario: default weights
- GIVEN a model snapshot with hit_rate=0.8, average_matches=2.5, consistency_score=0.9, precision=0.7, recall=0.6
- WHEN scoring with default weights
- THEN score = 0.8×0.3 + 2.5×0.3 + 0.9×0.2 + 0.7×0.1 + 0.6×0.1 (after normalization)

#### Scenario: per-lottery weights override
- GIVEN lottery L with config_json containing custom weights
- WHEN ranking for lottery L
- THEN custom weights are used instead of defaults

#### Scenario: zero-weight sum rejected
- GIVEN weights where all values are 0.0
- WHEN validation runs
- THEN 422 VALIDATION_ERROR is returned

### META-002: Cross-Engine Normalization

The system SHALL normalize metrics per-engine using min-max normalization: `(value - min) / (max - min)`. Common metrics (hit_rate, average_matches, consistency_score, precision, recall, f1_score) are comparable across engines after normalization. Engine-specific metrics (best_fitness, total_draws_evaluated) SHALL be excluded from cross-engine ranking. Missing metrics SHALL be treated as 0.0 (conservative). consistency_score MUST be inverted (lower=better → higher=better) before scoring.

**Entities touched**: engine snapshot metrics (read-only)

#### Scenario: per-engine normalization
- GIVEN 3 ML snapshots and 2 BT snapshots with hit_rate values
- WHEN normalization runs
- THEN ML hit_rates normalized within ML set, BT hit_rates normalized within BT set, then compared

#### Scenario: engine-specific metric excluded
- GIVEN an OPT snapshot with best_fitness=0.95
- WHEN scoring
- THEN best_fitness is NOT included in the composite score

#### Scenario: missing metric defaults to 0.0
- GIVEN an ML snapshot missing precision
- WHEN scoring
- THEN precision contributes 0.0 to the composite score

### META-003: Context Resolution

The system SHALL resolve a context vector from existing DB columns: lottery_id, draws_from, draws_to, cut, window, engine_type. Context hash = SHA-256 of (lottery_id, draws_from, draws_to, cut, window, engine_type). No artificial features. All variables MUST exist in current schema.

**Entities touched**: draw, *_snapshots, exp_runs (read-only for context resolution)

#### Scenario: context hash is deterministic
- GIVEN identical context variables
- WHEN context is resolved twice
- THEN both hashes are identical

#### Scenario: context hash changes on variable change
- GIVEN a context with draws_to=2026-01-01
- WHEN draws_to changes to 2026-06-01
- THEN context hash differs

### META-004: Failed Run Exclusion

The system SHALL exclude snapshots with `status='failed'` from scoring and ranking. Failed runs SHALL NOT be penalized (score=None, not 0). Failed runs SHALL be tracked only in engine snapshot history, not in `meta_ranking_entries`.

**Entities touched**: engine snapshot status (read-only filter)

#### Scenario: failed snapshot excluded
- GIVEN a bt_snapshots row with status=failed
- WHEN ranking computation runs
- THEN that snapshot does not appear in meta_ranking_entries

#### Scenario: active snapshot included
- GIVEN a bt_snapshots row with status=active
- WHEN ranking computation runs
- THEN that snapshot appears in meta_ranking_entries with computed score

### META-005: Ranking

The system SHALL produce an immutable ranking snapshot ordered by composite score (descending). Sorting MUST use stable sort. Ranking SHALL be an atomic single-transaction write. New ranking supersedes old: old status → `retired`. Version MUST be monotonic per (lottery_id, context_hash): version = max(version) + 1.

**Entities touched**: `meta_rankings`, `meta_ranking_entries`

#### Scenario: ranking order
- GIVEN 4 models with scores 0.9, 0.7, 0.8, 0.6
- WHEN ranking snapshot is created
- THEN entries ordered: 0.9, 0.8, 0.7, 0.6 (descending)

#### Scenario: supersedes old ranking
- GIVEN an active ranking for (lottery_id=1, context_hash=X) with version=2
- WHEN a new ranking is computed for same context
- THEN old ranking status→retired, new ranking created with version=3, status=active

#### Scenario: stable sort preserves order for equal scores
- GIVEN two models with identical score
- WHEN ranking is created
- THEN their relative order is preserved (stable sort)

### META-006: Selection

The system SHALL select top-K models from a ranking where score ≥ min_score. Default top_k=5, min_score=0.0. top_k MUST be configurable per-lottery (min=1, max=20). Selection SHALL be an atomic single-transaction write producing an immutable snapshot.

**Entities touched**: `meta_selections`, `meta_selection_entries`

#### Scenario: top-K selection
- GIVEN a ranking with 10 models, top_k=5
- WHEN selection runs
- THEN top 5 models by score appear in meta_selection_entries

#### Scenario: threshold filtering
- GIVEN a ranking where 3 models score ≥ min_score and 7 score below
- WHEN selection runs with top_k=5
- THEN only the 3 qualifying models are selected

#### Scenario: insufficient qualifying models
- GIVEN a ranking where 2 models score ≥ min_score, top_k=5
- WHEN selection runs
- THEN 2 models are selected (less than K)

### META-007: Idempotency

The system SHALL detect duplicate operations via fingerprint. Same fingerprint = return existing active ranking/selection, skip recomputation. Fingerprint = SHA-256 of (lottery_id, context_hash, ranking_data).

**Entities touched**: `meta_rankings.fingerprint`, `meta_selections.fingerprint`

#### Scenario: idempotent ranking
- GIVEN an active ranking with fingerprint X
- WHEN POST /meta/rank produces same fingerprint
- THEN existing ranking is returned, no new rows written

#### Scenario: idempotent selection
- GIVEN an active selection with fingerprint X
- WHEN POST /meta/select produces same fingerprint
- THEN existing selection is returned, no new rows written

### META-008: Lifecycle

Rankings and selections SHALL follow lifecycle: `active|retired|failed`. Transitions: new→active, superseded→retired, error→failed. Only one `active` snapshot per (lottery_id, context_hash, fingerprint) at any time.

**Entities touched**: `meta_rankings.status`, `meta_selections.status`

#### Scenario: lifecycle transition
- GIVEN an active ranking
- WHEN a new ranking supersedes it
- THEN old→retired, new→active, atomic write

### META-009: Fingerprint

The system SHALL compute SHA-256 fingerprint over (lottery_id, context_hash, ranking_data). Fingerprint stored as VARCHAR(64). Used for idempotency: same fingerprint = same content.

**Entities touched**: `meta_rankings.fingerprint`, `meta_selections.fingerprint`

#### Scenario: different data produces different fingerprint
- GIVEN two rankings with same lottery_id but different context_hash
- WHEN both are created
- THEN their fingerprints differ

### META-010: History

All ranking and selection snapshots SHALL be retained (active + retired). History queryable by lottery_id, context_hash, status.

**Entities touched**: `meta_rankings`, `meta_selections`

#### Scenario: history retains retired
- GIVEN a superseded ranking (status=retired)
- WHEN history is queried
- THEN retired ranking appears in results

### META-011: Leakage Prevention

Ranking MUST use only metrics from snapshots with `draws_to` ≤ selection point. No future data enters scoring. Context hash includes `draws_to` to enforce temporal bound. Selection timestamp records selection point.

**Entities touched**: snapshot draws_to (read-only filter)

#### Scenario: future data excluded
- GIVEN snapshots with draws_to=2026-06-01 and draws_to=2026-12-01
- WHEN ranking is triggered on 2026-08-01
- THEN only snapshots with draws_to ≤ 2026-08-01 are scored

### META-012: lottery_id Isolation

Ranking and selection operations MUST be scoped per lottery. No cross-lottery ranking or selection.

**Entities touched**: all meta_* tables (filtered by lottery_id)

#### Scenario: isolated lotteries
- GIVEN lotteries A and B
- WHEN ranking runs for A
- THEN B's meta_* rows are unchanged

### META-013: API Endpoints

The system SHALL expose 4 endpoints: POST /meta/rank, GET /meta/ranking, POST /meta/select, GET /meta/selection. All use standard envelope `{success, data|error, timestamp}`.

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | /meta/rank | `{lottery_id, engine_types?, weights?}` | `{success, data: RankingResult}` | 404, 422 |
| GET | /meta/ranking | `?lottery_id&context_hash?` | `{success, data: RankingSnapshot}` | 404 |
| POST | /meta/select | `{lottery_id, top_k?, min_score?}` | `{success, data: SelectionResult}` | 404, 422 |
| GET | /meta/selection | `?lottery_id&context_hash?` | `{success, data: SelectionSnapshot}` | 404 |

#### Scenario: rank endpoint
- GIVEN a valid lottery_id with engine snapshots
- WHEN POST /meta/rank is called
- THEN ranking is computed and returned with entries

#### Scenario: lottery not found
- GIVEN lottery_id=999 does not exist
- WHEN POST /meta/rank is called
- THEN 404 NOT_FOUND error

### META-014: CLI Commands

The CLI SHALL expose `lip meta` subcommands: rank, ranking, select, selection. Behavior matches API. JSON output.

| Command | Args | Output |
|---------|------|--------|
| lip meta rank | --lottery-id, [--engine-types], [--weights] | JSON ranking |
| lip meta ranking | --lottery-id, [--context-hash] | JSON ranking snapshot |
| lip meta select | --lottery-id, [--top-k], [--min-score] | JSON selection |
| lip meta selection | --lottery-id, [--context-hash] | JSON selection snapshot |

#### Scenario: rank via CLI
- WHEN `lip meta rank --lottery-id 1`
- THEN ranking JSON is printed to stdout

### META-015: Persistence

The system SHALL persist to 4 tables in migration 0014 (additive, no existing table modified).

**meta_rankings**: id, lottery_id (FK→lottery.id RESTRICT), context_hash VARCHAR(64), version VARCHAR(32), status CHECK(active|retired|failed), fingerprint VARCHAR(64), config_json TEXT NULLABLE, created_at DATETIME(tz). Unique: (lottery_id, context_hash, fingerprint). Index: ix_meta_rankings_lottery_context on (lottery_id, context_hash).

**meta_ranking_entries**: id, ranking_id (FK→meta_rankings.id RESTRICT), model_id VARCHAR(100), engine_type CHECK(backtesting|ml|dl|optimization), score FLOAT, metrics_json TEXT, created_at DATETIME(tz). Index: ix_meta_ranking_entries_ranking on (ranking_id).

**meta_selections**: id, lottery_id (FK→lottery.id RESTRICT), context_hash VARCHAR(64), version VARCHAR(32), status CHECK(active|retired|failed), fingerprint VARCHAR(64), config_json TEXT NULLABLE, created_at DATETIME(tz). Unique: (lottery_id, context_hash, fingerprint). Index: ix_meta_selections_lottery_context on (lottery_id, context_hash).

**meta_selection_entries**: id, selection_id (FK→meta_selections.id RESTRICT), ranking_id (FK→meta_rankings.id RESTRICT), model_id VARCHAR(100), engine_type CHECK(backtesting|ml|dl|optimization), rank INTEGER, score FLOAT, created_at DATETIME(tz). Index: ix_meta_selection_entries_selection on (selection_id).

#### Scenario: migration creates tables
- GIVEN migration 0014
- WHEN alembic upgrade head runs
- THEN 4 meta_* tables exist with correct schema

#### Scenario: migration rollback
- GIVEN meta_* tables exist
- WHEN alembic downgrade -1 runs
- THEN only meta_* tables are dropped; no existing table modified

### META-016: Error Taxonomy

The system SHALL define `MetaServiceError` as subclass of `ServiceError`. Error codes:

| Error | HTTP | When |
|-------|------|------|
| META_RANKING_NOT_FOUND | 404 | Invalid lottery_id or context_hash |
| META_SELECTION_NOT_FOUND | 404 | Invalid lottery_id or context_hash |
| META_NO_ENGINE_DATA | 404 | No engine snapshots found for lottery |
| META_WEIGHTS_INVALID | 422 | Weights sum to zero or invalid format |
| META_TOP_K_INVALID | 422 | top_k < 1 or > 20 |
| META_DUPLICATE_RANKING | 409 | Same fingerprint, active ranking exists |

#### Scenario: no engine data
- GIVEN a lottery with no engine snapshots
- WHEN POST /meta/rank is called
- THEN 404 META_NO_ENGINE_DATA error

### META-017: Freshness Extension Point

The system SHALL include an optional `freshness_half_life_days` field in `config_json`. In MVP, this field MUST be ignored (treated as None). Architecture prepared for future freshness weighting without implementation.

**Entities touched**: `meta_rankings.config_json`

#### Scenario: freshness field ignored in MVP
- GIVEN config_json with freshness_half_life_days=30
- WHEN scoring runs
- THEN freshness weighting is NOT applied; score uses pure performance

### META-018: Boundary F11/F12/F13

F12 SHALL be read-only to exp_* tables (no writes). F12 MUST NOT execute engines. F12 MUST NOT generate combinations (F13 responsibility). F12 reads exp_* + engine metric tables, produces ranking/selection snapshots.

**Entities touched**: exp_* (read-only), engine metric tables (read-only)

#### Scenario: F12 does not write to exp_*
- WHEN ranking computation runs
- THEN no exp_* table rows are created or modified

### META-019: Weight Configuration

Default weights are global, overridable per-lottery via config_json on meta_rankings. Global defaults: hit_rate=0.3, average_matches=0.3, consistency_score=0.2, precision=0.1, recall=0.1. Per-lottery override replaces ALL defaults (no partial merge).

**Entities touched**: `meta_rankings.config_json`

#### Scenario: global defaults applied
- GIVEN a lottery with no custom weights in config_json
- WHEN scoring runs
- THEN default weights are used

### META-020: Top-K Defaults

Default top_k=5, configurable per-lottery in request params. Valid range: min=1, max=20. Default min_score=0.0.

**Entities touched**: request parameters

#### Scenario: default top-K
- GIVEN a ranking with 10 models
- WHEN POST /meta/select with no top_k param
- THEN top 5 models are selected

---

## Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-META-01 | Determinism | Same inputs → identical fingerprint and ranking order |
| NFR-META-02 | Idempotency | Same fingerprint returns existing active snapshot; no duplicate rows |
| NFR-META-03 | Immutability | Ranking/selection snapshots never mutated after persistence |
| NFR-META-04 | Isolation | All operations scoped per lottery_id; no cross-lottery contamination |
| NFR-META-05 | Performance | Ranking computation ≤ 500ms p95 for ≤ 1000 model snapshots |
| NFR-META-06 | Rollback | Migration 0014 downgrade drops only meta_* tables |
| NFR-META-07 | No new deps | NumPy only; no pandas, no new external packages |
| NFR-META-08 | Engine boundary | F12 reads engine tables via read-only queries; no engine imports at module level |
| NFR-META-09 | Error handling | All errors subclass ServiceError; map to correct HTTP codes |
| NFR-META-10 | Stability | Ranking uses stable sort (np.argsort kind='stable') |

## Traceability: Proposal → Requirements

| Proposal | Requirements |
|----------|--------------|
| Weighted scoring | META-001, META-019 |
| Cross-engine normalization | META-002 |
| Context resolution | META-003 |
| Failed runs | META-004 |
| Ranking | META-005, META-009, META-010 |
| Selection | META-006, META-020 |
| Idempotency | META-007 |
| Lifecycle | META-008 |
| Leakage prevention | META-011 |
| lottery_id isolation | META-012 |
| API/CLI | META-013, META-014 |
| Persistence | META-015 |
| Error taxonomy | META-016 |
| Freshness extension | META-017 |
| Boundary F11/F12/F13 | META-018 |

## Conflicts or Ambiguities

None. All 5 open questions resolved: Q1→global default weights (META-019), Q2→K=5 (META-020), Q3→freshness not in MVP (META-017), Q4→common metrics only (META-002), Q5→excluded entirely (META-004).

---

**Ready for design (sdd-design) upon confirmation.**
