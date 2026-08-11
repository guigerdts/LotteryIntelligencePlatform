# Proposal: Fase 12 — Meta Learning

## 1. Problem Statement

F12 solves the **model selection problem**: after F7/F8/F9/F10 produce trained models and F11 tracks experiments, there is no systematic way to evaluate, rank, and select the best-performing models per context. Currently, model selection is ad-hoc or manual. F12 provides a deterministic, transparent scoring and ranking system that consumes persisted engine outputs and produces ranked selections for F13 consumption.

## 2. Goals

- Compute weighted scores for all model/strategy snapshots across engines (ML/DL/OPT/BT)
- Rank models per context (lottery + draw characteristics + engine type)
- Select top-K models per context for F13 generation
- Persist ranking snapshots and selection history as immutable records
- Provide API/CLI surface for ranking and selection operations
- Ensure determinism: same inputs → same ranking

## 3. Non-Goals

- No model training or evaluation (F7/F8/F9/F10)
- No combination generation (F13)
- No UI/dashboard (F14)
- No real-time selection (batch only)
- No learned meta-model (weighted sum for MVP)
- No online learning or adaptive scoring
- No cross-lottery comparison
- No experiment management (F11)

## 4. Proposed Architecture

### Module Structure
```
backend/src/backend/app/meta/
├── __init__.py
├── scoring.py          # Weighted scoring engine
├── normalization.py    # Cross-engine metric normalization
├── ranking.py          # Ranking computation and snapshot
├── selection.py        # Top-K selection logic
├── context.py          # Context vector resolution
├── snapshot_store.py   # meta_* persistence (lifecycle pattern)
└── types.py            # Dataclasses for scoring/ranking
```

### Service Layer
- `MetaService` — orchestrates scoring → ranking → selection
- `MetaSnapshotStore` — persistence following BTE-10 pattern

### API/CLI
- `POST /meta/rank` — trigger ranking computation
- `GET /meta/ranking` — retrieve ranking snapshot
- `POST /meta/select` — trigger selection
- `GET /meta/selection` — retrieve selection history
- `lip meta rank|ranking|select|selection`

### Persistence
- `meta_rankings` — ranking snapshot header
- `meta_ranking_entries` — scored model entries
- `meta_selections` — selection snapshot header
- `meta_selection_entries` — selected model entries

## 5. Data Flow

```
Engine Metrics (ml_metrics, dl_metrics, opt_results, bt_results)
    ↓
F12 Context Resolution (lottery_id + draw characteristics)
    ↓
F12 Scoring (weighted sum across normalized metrics)
    ↓
F12 Ranking (sorted by score, immutable snapshot)
    ↓
F12 Selection (top-K from ranking)
    ↓
F13 Consumption (selected models for generation)
```

## 6. Context Definition (CRITICAL)

**Context Vector** (derived from existing DB columns only):

| Variable | Source | Type |
|----------|--------|------|
| `lottery_id` | `draw.lottery_id` | int |
| `draw_number` | `draw.draw_number` | int |
| `draw_date` | `draw.draw_date` | datetime |
| `jackpot` | `draw.jackpot` | decimal |
| `winners` | `draw.winners` | int |
| `draws_from` | `*_snapshots.draws_from` | datetime |
| `draws_to` | `*_snapshots.draws_to` | datetime |
| `cut` | `ml_snapshots.cut`, `dl_snapshots.cut` | datetime |
| `window` | `dl_snapshots.window` | int |
| `engine_type` | `exp_runs.engine_type` | string |
| `snapshot_version` | `*_snapshots.version` | string |
| `snapshot_status` | `*_snapshots.status` | string |

**Context Hash**: SHA-256 of (lottery_id, draws_from, draws_to, cut, window, engine_type)

**No artificial features.** All variables exist in current schema.

## 7. Scoring Proposal (CRITICAL)

### Recommendation: Weighted Deterministic Scoring (MVP)

**Why weighted sum over alternatives:**
- **Transparent**: weights are configurable, explainable
- **Deterministic**: same inputs → same score
- **Interpretable**: human can verify ranking logic
- **No pandas needed**: NumPy + pure Python
- **No learned model**: avoids overfitting and opacity

**Scoring Algorithm**:
```python
def compute_score(metrics: dict[str, float], weights: dict[str, float]) -> float:
    """Weighted sum of normalized metrics."""
    return sum(metrics[k] * weights.get(k, 0.0) for k in metrics if k in weights)
```

**Default Weights** (configurable per lottery):
- `hit_rate`: 0.3
- `average_matches`: 0.3
- `consistency_score`: 0.2
- `precision`: 0.1
- `recall`: 0.1

**Failure Handling**: Failed runs excluded from scoring (score = None, not 0).

## 8. Cross-Engine Normalization (CRITICAL)

### Common Metric Vocabulary

| Metric | ML | DL | OPT | BT | Notes |
|--------|----|----|-----|-----|-------|
| hit_rate | ✓ | ✓ | — | ✓ | Direct comparison |
| average_matches | ✓ | ✓ | — | ✓ | Direct comparison |
| consistency_score | ✓ | ✓ | — | ✓ | Direct comparison (lower=better) |
| precision | ✓ | ✓ | — | — | Direct comparison |
| recall | ✓ | ✓ | — | — | Direct comparison |
| f1_score | ✓ | ✓ | — | — | Direct comparison |
| best_fitness | — | — | ✓ | — | OPT-specific, exclude from cross-engine |
| total_draws_evaluated | — | — | — | ✓ | Context only, not scored |

### Normalization Strategy

**Per-engine normalization** (within same engine type):
- Min-max normalization: `(value - min) / (max - min)`
- Applied to metrics within each engine type before cross-engine comparison

**Cross-engine normalization**:
- Common metrics (hit_rate, average_matches) compared directly after per-engine normalization
- Engine-specific metrics (best_fitness) excluded from cross-engine ranking
- Missing metrics treated as 0.0 (conservative)

**Implementation**: NumPy `np.min()`, `np.max()` for normalization.

## 9. Ranking

### Definition
A ranking is an immutable snapshot of scored models at a point in time, ordered by composite score.

### Immutability
- Follows snapshot pattern from F7-F11 (`active|retired|failed`)
- Once persisted, never mutated
- New ranking supersedes old (old → `retired`)

### Determinism Guarantees
- Same inputs (context + metrics + weights) → same ranking
- Sorting uses stable sort (NumPy `np.argsort` with kind='stable')
- No stochastic elements in MVP

### Idempotency Rules
- Same fingerprint (lottery_id + context_hash + ranking_data) → return existing
- Recomputing with same data produces same fingerprint

### Versioning
- Monotonic version per (lottery_id, context_hash)
- Version = max(version) + 1

## 10. Selection

### Strategy: Top-K + Threshold

**Why top-K + threshold:**
- Top-K ensures bounded output for F13
- Threshold ensures minimum quality bar
- Both deterministic and reproducible

**Configuration**:
- `top_k`: int (default 5, configurable per lottery)
- `min_score`: float (default 0.0, configurable)
- Selection = top-K models where score ≥ min_score

### Selection Logic
1. Take ranking snapshot
2. Filter entries where score ≥ min_score
3. Take top-K from filtered entries
4. Persist as immutable selection snapshot

### F13 Compatibility
- Selection provides ordered list of (model_id, score, engine_type)
- F13 consumes selection to generate combinations

## 11. History/Versioning

### Persistence Pattern
- Immutable snapshots (active|retired|failed)
- Fingerprint: SHA-256 of (lottery_id, context_hash, ranking_data)
- Version: monotonic per (lottery_id, context_hash)
- History: all snapshots retained (active + retired)

### Tables
- `meta_rankings`: header (lottery_id, context_hash, version, status, fingerprint, created_at)
- `meta_ranking_entries`: entries (ranking_id, model_id, engine_type, score, metrics_json)
- `meta_selections`: header (lottery_id, context_hash, version, status, fingerprint, created_at)
- `meta_selection_entries`: entries (selection_id, ranking_id, model_id, engine_type, rank, score)

## 12. Leakage Prevention

### Temporal Boundaries
- Ranking uses only metrics from snapshots with `draws_to` ≤ selection point
- No future data enters scoring
- Context hash includes `draws_to` to enforce temporal bound

### Train/Evaluation Separation
- Metrics from engine snapshots already respect train/eval separation (F7-F10)
- F12 uses persisted metrics only, not raw data

### No Retrospective Selection
- Selection snapshot timestamp records selection point
- Cannot retroactively select models based on later data

## 13. Failed Runs

### Decision: Excluded from Scoring
- Failed snapshots (`status='failed'`) excluded from ranking
- Not penalized (score = None, not 0)
- Tracked separately in snapshot history

### Rationale
- Failed runs indicate execution errors, not performance
- Penalizing would bias ranking toward "never tried"
- Exclusion is deterministic and transparent

## 14. Freshness/Context Drift

### Freshness Weighting (Optional, Configurable)
- Default: no freshness weighting (pure performance)
- Optional: exponential decay based on `draws_to` recency
- Configuration: `freshness_half_life_days` (default: None = disabled)

### Context Versioning
- Context hash changes when context variables change
- Old rankings remain valid for old contexts
- New context → new ranking computation

### Staleness Prevention
- Ranking triggered manually (no scheduler)
- User decides when to refresh ranking
- Stale rankings flagged by timestamp comparison

## 15. Proposed Persistence

### Tables (Migration 0014)

**`meta_rankings`**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| lottery_id | Integer FK → lottery.id | RESTRICT, NOT NULL |
| context_hash | String(64) | NOT NULL |
| version | String(32) | NOT NULL |
| status | String(16) | CHECK active\|retired\|failed |
| fingerprint | String(64) | SHA-256, NOT NULL |
| config_json | Text | NULLABLE |
| created_at | DateTime(tz) | NOT NULL |

**Unique**: `(lottery_id, context_hash, fingerprint)`
**Index**: `ix_meta_rankings_lottery_context` on `(lottery_id, context_hash)`

**`meta_ranking_entries`**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| ranking_id | Integer FK → meta_rankings.id | RESTRICT, NOT NULL |
| model_id | String(100) | NOT NULL |
| engine_type | String(20) | CHECK backtesting\|ml\|dl\|optimization |
| score | Float | NOT NULL |
| metrics_json | Text | NOT NULL |
| created_at | DateTime(tz) | NOT NULL |

**Index**: `ix_meta_ranking_entries_ranking` on `(ranking_id)`

**`meta_selections`**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| lottery_id | Integer FK → lottery.id | RESTRICT, NOT NULL |
| context_hash | String(64) | NOT NULL |
| version | String(32) | NOT NULL |
| status | String(16) | CHECK active\|retired\|failed |
| fingerprint | String(64) | SHA-256, NOT NULL |
| config_json | Text | NULLABLE |
| created_at | DateTime(tz) | NOT NULL |

**Unique**: `(lottery_id, context_hash, fingerprint)`
**Index**: `ix_meta_selections_lottery_context` on `(lottery_id, context_hash)`

**`meta_selection_entries`**
| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| selection_id | Integer FK → meta_selections.id | RESTRICT, NOT NULL |
| ranking_id | Integer FK → meta_rankings.id | RESTRICT, NOT NULL |
| model_id | String(100) | NOT NULL |
| engine_type | String(20) | CHECK backtesting\|ml\|dl\|optimization |
| rank | Integer | NOT NULL |
| score | Float | NOT NULL |
| created_at | DateTime(tz) | NOT NULL |

**Index**: `ix_meta_selection_entries_selection` on `(selection_id)`

### Table Count Validation
- 4 tables justified: rankings (header + entries), selections (header + entries)
- Follows pattern: bt_snapshots/bt_results, ml_snapshots/ml_metrics
- Separation of concerns: ranking ≠ selection

## 16. Proposed API/CLI

### API Endpoints

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | /meta/rank | `{lottery_id, engine_types?, weights?}` | `{success, data: RankingResult}` | 404, 422 |
| GET | /meta/ranking | `?lottery_id&context_hash?` | `{success, data: RankingSnapshot}` | 404 |
| POST | /meta/select | `{lottery_id, top_k?, min_score?}` | `{success, data: SelectionResult}` | 404, 422 |
| GET | /meta/selection | `?lottery_id&context_hash?` | `{success, data: SelectionSnapshot}` | 404 |

### CLI Commands

| Command | Args | Output |
|---------|------|--------|
| lip meta rank | --lottery-id, [--engine-types], [--weights] | JSON ranking |
| lip meta ranking | --lottery-id, [--context-hash] | JSON ranking snapshot |
| lip meta select | --lottery-id, [--top-k], [--min-score] | JSON selection |
| lip meta selection | --lottery-id, [--context-hash] | JSON selection snapshot |

## 17. Dependencies

- **No new external dependencies**
- NumPy (2.2.6) already available for normalization
- Read-only access to: `exp_*`, `ml_*`, `dl_*`, `opt_*`, `bt_*`, `draw`
- No pandas requirement (explicit constraint)

## 18. Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Leakage from future data | Medium | Temporal boundaries enforced via `draws_to` |
| Overfitting to historical | Medium | Use out-of-sample metrics only (from engine snapshots) |
| Survivorship bias | Medium | Include all models, including failed runs (excluded from scoring) |
| Cross-engine metric incompatibility | High | Per-engine normalization, common metrics only |
| Complexity creep | Low | Start with weighted sum, iterate only if needed |
| Determinism challenges | Low | No stochastic elements, stable sort |
| Dependency on F11 changes | Low | Document assumptions, version context hash |

## 19. Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1: Scoring algorithm | Weighted sum | Transparent, deterministic, interpretable, no pandas |
| D2: Context definition | Minimal, data-driven | Only existing DB columns, no artificial features |
| D3: Cross-engine normalization | Per-engine min-max | Fair comparison, common metrics only |
| D4: Selection strategy | Top-K + threshold | Bounded output, minimum quality, deterministic |
| D5: Ranking immutability | Snapshot pattern | Follows F7-F11 convention, audit trail |

## 20. Open Questions Still Needing Authorization

1. **Weight Configuration**: Should weights be per-lottery or global? (Recommendation: per-lottery, stored in `config_json`)
2. **Top-K Default**: What is the default K? (Recommendation: 5)
3. **Freshness Weighting**: Should MVP include optional freshness decay? (Recommendation: no, add later if needed)
4. **Metric Exclusion**: Which engine-specific metrics to exclude from cross-engine ranking? (Recommendation: `best_fitness` excluded)
5. **Failure Handling**: Should failed runs be tracked in ranking entries with score=None? (Recommendation: excluded entirely)

## 21. Boundary F11/F12/F13

| Phase | Responsibility | Input | Output |
|-------|----------------|-------|--------|
| F11 Experiment | Register, version, compare, export experiments | Engine snapshots | `exp_*` tables, comparison JSON |
| F12 Meta Learning | Evaluate, rank, select models | `exp_*` + engine metrics + context | Ranking snapshots, selection history |
| F13 Generator | Generate combinations, filter, evaluate | Selected models from F12 | Number combinations |

### Non-Duplication Rules
- F12 does NOT duplicate F11 comparison logic (can use F11's comparison_json or recompute)
- F12 does NOT execute engines (read-only to engine tables)
- F12 does NOT generate combinations (F13 responsibility)
- F12 does NOT provide UI (F14 responsibility)
- F12 reads `exp_*` tables but does NOT write to them

---

**Ready for specs (sdd-spec) upon confirmation.**
