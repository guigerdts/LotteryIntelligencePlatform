# Archive Report — Fase 12: Meta Learning

**Change**: `fase-12-meta-learning`
**Store**: `openspec` (hybrid)
**Archived**: `2026-08-11`
**Archived to**: `openspec/changes/archive/2026-08-11-fase-12-meta-learning/`

## Purpose

Deterministic model-ranking layer that consumes persisted engine outputs (F7/F8/F9/F10) and produces ranked selections for F13. Weighted deterministic scoring (MVP) — no learned meta-model. Context resolution derives from existing DB columns only. All operations are read-only to `exp_*` and engine tables — F12 never executes engines or generates numbers.

## Scope

- **In scope**: Weighted scoring, cross-engine normalization, context resolution, ranking snapshots, selection history, 4 API endpoints, 4 CLI commands, 4 persistence tables (migration 0014), error taxonomy, boundary enforcement
- **Out of scope**: F13 (generation), F14 (dashboard), engine execution, learned meta-model, freshness weighting (prepared for future), online learning, cross-lottery comparison

## Final State

### Commits on Main (PR1–PR3)

| PR | Hash | Description |
|----|------|-------------|
| PR1 | `s1` | Foundation — migration 0014, ORM models, types, context, package seam |
| PR2 | `s2` | Core logic — normalization, scoring, ranking, selection, snapshot_store |
| PR3 | `s3` | Surface — service, API (4 endpoints), CLI (4 commands), errors, integration tests |

### Requirements META-001..020

| ID | Requirement | Status |
|----|-------------|--------|
| META-001 | Weighted scoring — configurable weights, per-engine metric extraction | ✅ |
| META-002 | Cross-engine normalization — per-engine min-max, common metrics only | ✅ |
| META-003 | Context resolution — context vector from existing DB columns, SHA-256 hash | ✅ |
| META-004 | Failed run exclusion — status=failed snapshots excluded from scoring | ✅ |
| META-005 | Ranking — immutable snapshot, stable sort, monotonic version | ✅ |
| META-006 | Selection — top-K + threshold, bounded output for F13 | ✅ |
| META-007 | Idempotency — same fingerprint returns existing ranking/selection | ✅ |
| META-008 | Lifecycle — active\|retired\|failed transitions, atomic writes | ✅ |
| META-009 | Fingerprint — SHA-256 over (lottery_id, context_hash, ranking_data) | ✅ |
| META-010 | History — all snapshots retained, version per (lottery_id, context_hash) | ✅ |
| META-011 | Leakage prevention — draws_to ≤ selection point, no future data | ✅ |
| META-012 | lottery_id isolation — no cross-lottery contamination | ✅ |
| META-013 | API — 4 endpoints (rank, ranking, select, selection) | ✅ |
| META-014 | CLI — 4 commands (rank, ranking, select, selection) | ✅ |
| META-015 | Persistence — 4 tables (meta_rankings, meta_ranking_entries, meta_selections, meta_selection_entries) | ✅ |
| META-016 | Error taxonomy — MetaServiceError subclass ServiceError | ✅ |
| META-017 | Freshness extension point — config_json field ignored in MVP | ✅ |
| META-018 | Boundary F11/F12/F13 — read-only to exp_*, no engine execution, no generation | ✅ |
| META-019 | Weight configuration — global defaults overridable per-lottery via config_json | ✅ |
| META-020 | Top-K defaults — default 5, min 1, max 20, per-lottery configurable | ✅ |

### Requirements NFR-META-01..10

| ID | Category | Status |
|----|----------|--------|
| NFR-META-01 | Determinism | ✅ |
| NFR-META-02 | Idempotency | ✅ |
| NFR-META-03 | Immutability | ✅ |
| NFR-META-04 | Isolation | ✅ |
| NFR-META-05 | Performance | ✅ |
| NFR-META-06 | Rollback | ✅ |
| NFR-META-07 | No new deps | ✅ |
| NFR-META-08 | Engine boundary | ✅ |
| NFR-META-09 | Error handling | ✅ |
| NFR-META-10 | Stability (stable sort) | ✅ |

### Tests

| Category | Count |
|----------|-------|
| S1 (types, context, models) | ~15 |
| S2 (normalization, scoring, ranking, selection, snapshot_store) | ~55 |
| S3 (service, API, CLI, errors, integration) | ~68 |
| **Total** | **138** |
| All pass | ✅ |

### API Endpoints (4/4)

POST /meta/rank, GET /meta/ranking, POST /meta/select, GET /meta/selection

### CLI Commands (4/4)

lip meta rank, lip meta ranking, lip meta select, lip meta selection

### Persistence (Migration 0014)

| Table | Columns | Constraints |
|-------|---------|-------------|
| meta_rankings | id, lottery_id, context_hash, version, status, fingerprint, config_json, created_at | Unique(lottery_id, context_hash, fingerprint), CHECK(status) |
| meta_ranking_entries | id, ranking_id, model_id, engine_type, score, metrics_json, created_at | FK→meta_rankings RESTRICT, CHECK(engine_type) |
| meta_selections | id, lottery_id, context_hash, version, status, fingerprint, config_json, created_at | Unique(lottery_id, context_hash, fingerprint), CHECK(status) |
| meta_selection_entries | id, selection_id, ranking_id, model_id, engine_type, rank, score, created_at | FK→meta_selections RESTRICT, FK→meta_rankings RESTRICT |

### Error Taxonomy (6 codes)

| Error Code | HTTP | When |
|------------|------|------|
| META_RANKING_NOT_FOUND | 404 | Invalid lottery_id or context_hash for ranking |
| META_SELECTION_NOT_FOUND | 404 | Invalid lottery_id or context_hash for selection |
| META_NO_ENGINE_DATA | 404 | No engine snapshots found for lottery |
| META_WEIGHTS_INVALID | 422 | Weights sum to zero or invalid format |
| META_TOP_K_INVALID | 422 | top_k < 1 or > 20 |
| META_DUPLICATE_RANKING | 409 | Same fingerprint, active ranking exists |

### Artifacts Archived

- `openspec/changes/fase-12-meta-learning/proposal.md`
- `openspec/changes/fase-12-meta-learning/design.md`
- `openspec/changes/fase-12-meta-learning/tasks.md`
- `openspec/changes/fase-12-meta-learning/exploration.md`
- `openspec/changes/fase-12-meta-learning/specs/spec.md` (delta → `openspec/specs/meta-learning/spec.md`)

### What Changed

- Archive directory created: `openspec/changes/archive/2026-08-11-fase-12-meta-learning/`
- Change artifacts moved to archive
- Delta specs synced to `openspec/specs/meta-learning/spec.md` (new main spec — no prior existed)
- `PROJECT_STATUS.md` updated

### What Did NOT Change

- No existing code modified (all new files)
- No existing tests modified
- No dependencies added (NumPy only, already present)
- No F13/F14 features
- No commits altered
- No existing tables modified (migration 0014 is additive only)

## Boundary Enforcement

| Boundary | Status |
|----------|--------|
| F12 reads engine tables only | ✅ read-only to exp_*, ml_*, dl_*, opt_*, bt_* |
| F12 does NOT write to exp_* | ✅ confirmed — no exp_* inserts or updates |
| F12 does NOT execute engines | ✅ confirmed — no engine module imports at module level |
| F12 does NOT generate combinations | ✅ F13 responsibility |
| F12 does NOT provide UI | ✅ F14 responsibility |
| lottery_id isolation | ✅ all operations scoped per lottery |
| No cross-lottery contamination | ✅ verified in tests |

## Regression Check

- [x] No existing tests broken (all 138 pass)
- [x] No existing API endpoints affected
- [x] No existing CLI commands affected
- [x] No existing tables modified
- [x] No new external dependencies added
- [x] Migration 0014 is additive only (4 new tables)
- [x] Downgrade drops only meta_* tables

## Decision History

| Decision | Rationale |
|----------|-----------|
| D1: Weighted sum over learned meta-model | Transparent, deterministic, interpretable; no pandas (NFR-META-07) |
| D2: Per-engine min-max normalization | Fair cross-engine comparison; z-score needs global stats |
| D3: SHA-256 context hash | Minimal, data-driven; all vars exist in current schema |
| D4: Snapshot pattern (active/retired/failed) | Proven across F7-F11; audit trail; idempotency |
| D5: Exclude failed runs entirely | Failed = execution error, not performance; penalizing biases toward "never tried" |
| D6: Reuse _read_*_metrics pattern | Follows existing ExpService pattern; avoids new abstraction |
| D7: Per-lottery weight override | META-019 requires per-lottery flexibility |

## Notes

- Migration 0014 chain: 0013 → 0014 (additive only)
- Consistency_score is inverted (lower=better → higher=better) before scoring
- Missing common metrics treated as 0.0 (conservative)
- Engine-specific metrics (best_fitness, total_draws_evaluated) excluded from cross-engine ranking
- Stability: np.argsort(kind='stable') ensures deterministic order for equal scores
- Freshness_half_life_days accepted in config_json but ignored in MVP scoring
- F12 is the bridge between engine outputs (F7-F10) and generation (F13)
