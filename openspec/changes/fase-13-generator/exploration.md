# Exploration: Fase 13 — Intelligent Generator

**Change**: `fase-13-generator` · **Date**: 2026-08-11 · **Phase**: sdd-explore

## 1. Current State

### Backend Module Structure
- **Core Domain**: `lottery`, `draw`, `draw_numbers`, `super_number`, `datasets`, `dataset_draws`
- **Engines**: Statistics (F3), Feature (F4), Probability (F5), Graph (F6), ML (F7), DL (F8), Optimization (F9), Backtesting (F10), Experiment (F11), Meta Learning (F12)
- **Migration Head**: 0014 (F12 Meta Learning tables)
- **Existing Engines with Number Generation**:
  - Probability Engine (F5): `monte_carlo()` generates random selections via isolated `random.Random(seed)`
  - Backtesting Benchmarks (F10): `UniformRandomBenchmark` and `HypergeometricBenchmark` generate predictions
  - Strategy Protocol: `predict(draw_context) -> list[int]` interface for ML/DL/BT strategies

### F12 Selection Snapshot Structure (F13 Input)
- **`meta_selections`** header: `id`, `lottery_id`, `context_hash`, `version`, `status`, `fingerprint`, `config_json`, `created_at`
- **`meta_selection_entries`**: `selection_id`, `ranking_id`, `model_id` (String(100)), `engine_type` (CHECK: backtesting|ml|dl|optimization), `rank` (Integer), `score` (Float)

### Lottery Config (Number Ranges)
- **`lottery`** table: `min_number`, `max_number`, `numbers_to_select`, `super_number_min`, `super_number_max`
- Example: Lottery with min=1, max=50, numbers_to_select=6, super_number_min=1, super_number_max=10

### Draw Format
- **`draw`** table: `lottery_id`, `draw_number`, `draw_date`, `jackpot`, `winners`
- **`draw_numbers`**: `draw_id`, `position`, `number` (sorted list of main numbers)
- **`super_number`**: `draw_id`, `value` (optional 0..1 super number)

## 2. F12 Contracts Exposed for F13

### Selection Entry Fields
```python
@dataclass(frozen=True)
class SelectionEntry:
    model_id: str      # e.g., "ml-core-5", "dl-core-3", "bt-strategy-1"
    engine_type: str   # "backtesting", "ml", "dl", "optimization"
    rank: int          # Position in selection (1, 2, 3, ...)
    score: float       # Normalized score from F12 ranking
```

### What F12 Produces
1. **Ranked selection** of top-K models per (lottery_id, context_hash)
2. **Model identifiers** (`model_id`) that reference engine snapshots
3. **Engine types** that indicate which engine produced the model
4. **Scores** that indicate relative performance

### What F13 Consumes
- Active selection snapshot for a lottery
- Selection entries with model_id, engine_type, rank, score
- Lottery config (number ranges, super number)
- Historical draws (for context/prediction)

## 3. What F13 Needs to Generate

### Core Question: What does "generate" mean?
Based on codebase analysis, F13 could mean:

**Option A: Model-Based Prediction**
- Load model artifacts from DB (DL weights BLOB, ML models)
- Use `StrategyProtocol.predict(draw_context)` to generate predictions
- Problem: Model artifacts may not be persisted for all engine types; ML models are in-memory

**Option B: Probability-Weighted Generation**
- Use F12 selection scores to weight probability distributions
- Generate combinations using weighted random sampling
- Leverages existing probability engine infrastructure

**Option C: Hybrid Approach**
- Combine model predictions with probability distributions
- Use selection scores to blend multiple generation strategies
- Most flexible but most complex

**Option D: Strategy Execution**
- Execute selected strategies (ML/DL/BT) on current context
- Use their predictions directly as generated combinations
- Requires model artifact loading and inference

### Realistic Scope for F13 MVP
Given the codebase state, **Option B (Probability-Weighted Generation)** is most feasible:
1. Read selection entries from F12
2. Map `model_id` to per-number probability weights (from engine metrics or selection scores)
3. Generate combinations using weighted random sampling (reusing probability engine patterns)
4. Persist generated combinations with metadata

## 4. Reusable Components

### Already Existing
- **Probability Engine** (F5): `monte_carlo()`, `empirical()`, `hypergeometric()` — can be adapted for generation
- **Determinism Pattern**: `random.Random(seed)` isolation for reproducibility
- **Snapshot Pattern**: `active|retired|failed` lifecycle, SHA-256 fingerprints, monotonic versioning
- **Lottery Repository**: `LotteryRepository` for config access
- **Draw Repository**: Historical draw access for context
- **Backtesting Benchmarks**: `UniformRandomBenchmark`, `HypergeometricBenchmark` — number generation patterns

### Can Be Adapted
- **`BtSnapshotStore`** pattern: Atomic writes, lifecycle transitions, fingerprint idempotency
- **`MetaSnapshotStore`** pattern: Version management, fingerprint lookup
- **Strategy Protocol**: `predict(draw_context) -> list[int]` interface

## 5. Exact F12/F13 Boundary

### F12 Produces (F13 Consumes)
- Active selection snapshot with ranked model entries
- Model identifiers and engine types
- Performance scores for weighting

### F13 Must NOT Re-Implement
- Ranking/scoring logic (F12 responsibility)
- Engine execution (F7/F8/F9/F10 responsibility)
- Model training (F7/F8 responsibility)
- Experiment tracking (F11 responsibility)

### F13 Responsibilities
- Generate number combinations based on selected models
- Persist generated combinations with metadata
- Provide deterministic, reproducible generation
- Expose API/CLI for generation operations

## 6. Leakage, Reproducibility, Determinism Risks

### Leakage Risks
- **Future Data**: Generation must not use draws beyond the selection point (`draws_to`)
- **Model Leakage**: Selected models may have been trained on data including future draws
- **Mitigation**: Use `context_hash` from F12 which includes `draws_to` temporal bound

### Reproducibility Risks
- **Random Seed**: Must use isolated `random.Random(seed)` (not global random)
- **Model Loading**: If loading model artifacts, must ensure identical inference
- **Probability Weights**: Must be deterministic given same selection and lottery config

### Determinism Guarantees Needed
- Same selection + same lottery config + same seed = identical combinations
- Same fingerprint for identical generation parameters
- Version monotonicity per (lottery_id, selection_id)

## 7. Real Dependencies

### F13 Depends On
- **F12 Selection**: `meta_selections` + `meta_selection_entries` (active snapshot)
- **Lottery Config**: `lottery` table (number ranges, super number)
- **Historical Draws**: `draw` + `draw_numbers` + `super_number` (for context)
- **Probability Engine** (optional): For weighted generation patterns

### F13 Does NOT Depend On
- Engine execution (F7/F8/F9/F10)
- Model artifacts (unless implementing Option A/D)
- Experiment tables (F11)
- Dashboard (F14)

## 8. What F13 Should Persist

### Following Existing Patterns (F7-F12)
F13 would likely need:

**Option 1: Simple Combination Table**
```sql
CREATE TABLE generated_combinations (
    id INTEGER PRIMARY KEY,
    lottery_id INTEGER NOT NULL REFERENCES lottery(id),
    selection_id INTEGER NOT NULL REFERENCES meta_selections(id),
    numbers TEXT NOT NULL,  -- JSON array of main numbers
    super_number INTEGER,   -- Optional super number
    seed INTEGER,           -- Reproducibility seed
    fingerprint VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL
);
```

**Option 2: Snapshot Pattern (Consistent with F7-F12)**
```sql
-- Generation snapshot header
CREATE TABLE gen_snapshots (
    id INTEGER PRIMARY KEY,
    lottery_id INTEGER NOT NULL REFERENCES lottery(id),
    selection_id INTEGER NOT NULL REFERENCES meta_selections(id),
    version VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('active', 'retired', 'failed')),
    fingerprint VARCHAR(64) NOT NULL,
    config_json TEXT,  -- Generation parameters (seed, count, weights)
    created_at DATETIME NOT NULL,
    UNIQUE(lottery_id, selection_id, fingerprint)
);

-- Generated combinations
CREATE TABLE gen_combinations (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES gen_snapshots(id),
    position INTEGER NOT NULL,  -- Order within snapshot
    numbers TEXT NOT NULL,      -- JSON array of main numbers
    super_number INTEGER,       -- Optional super number
    score FLOAT,               -- Optional combination score
    created_at DATETIME NOT NULL
);
```

### Recommended: Option 2 (Snapshot Pattern)
- Follows proven pattern from F7-F12
- Enables lifecycle management (active|retired|failed)
- Supports idempotency via fingerprint
- Allows version history
- Consistent with project architecture

## 9. API/CLI Scope

### Following F12 Pattern (4 endpoints, 4 commands)
F13 would likely expose:

**API Endpoints**:
- `POST /gen/generate` — Trigger combination generation
- `GET /gen/combinations` — Retrieve generated combinations
- `POST /gen/evaluate` — Evaluate combinations against criteria
- `GET /gen/evaluation` — Retrieve evaluation results

**CLI Commands**:
- `lip gen generate` — Generate combinations
- `lip gen combinations` — List generated combinations
- `lip gen evaluate` — Evaluate combinations
- `lip gen evaluation` — Show evaluation results

### Scope Question
Do we need evaluation in F13 MVP? Or just generation + persistence?

## 10. Conflicts with F11/F12

### No Conflicts Expected
- **F11**: Tracks experiments; F13 generates combinations (different concern)
- **F12**: Ranks/selects models; F13 uses selection to generate (different operation)
- **F7-F10**: Execute engines; F13 uses selection output (read-only dependency)

### Potential Overlap
- **Generation Logic**: F5 probability engine has `monte_carlo()` which generates random selections
- **Decision**: F13 should extend/refactor probability engine or create new generation-specific logic?

## 11. Initial F13 Architecture Proposal

### Module Structure
```
backend/src/backend/app/generators/
├── __init__.py              # Package seam (docstring only)
├── types.py                 # GenerationConfig, Combination, GenerationResult
├── resolver.py              # resolve_generation_context(), map_selection_to_weights()
├── engine.py                # generate_combinations(), weighted_random_sample()
├── fingerprint.py           # compute_generation_fingerprint()
├── snapshot_store.py        # GenSnapshotStore — gen_* I/O owner (lifecycle pattern)
└── version.py               # GENERATOR_VERSION constant

backend/src/backend/app/models/
├── gen_snapshot.py          # GenSnapshot ORM model
├── gen_combination.py       # GenCombination ORM model

backend/src/backend/app/services/
├── gen_service.py           # GenService — composition root (generate, get_combinations)

backend/src/backend/app/api/v1/
├── gen.py                   # API router (4 endpoints)

backend/src/backend/app/schemas/
├── gen.py                   # Pydantic v2 schemas (request/response)

backend/alembic/versions/
├── 0015_gen_tables.py       # Migration (gen_* tables)

backend/tests/gen/
├── __init__.py
├── test_types.py
├── test_resolver.py
├── test_engine.py
├── test_snapshot_store.py
├── test_gen_service.py
├── test_gen_api.py
└── test_gen_cli.py
```

### Key Design Decisions
1. **Use Snapshot Pattern**: Consistent with F7-F12, enables lifecycle management
2. **Leverage Probability Engine**: Adapt `monte_carlo()` patterns for weighted generation
3. **Deterministic Generation**: Isolated `random.Random(seed)` for reproducibility
4. **Selection-Driven**: Use F12 selection scores to weight generation
5. **Lottery-Aware**: Respect lottery config (number ranges, super number)

## 12. Open Questions

### Critical Questions (Must Answer Before Design)
1. **What exactly does F13 generate?**
   - Number combinations per lottery?
   - How many combinations per generation run?
   - What constraints (if any) on combinations?

2. **How does F13 use selected models?**
   - Load model artifacts and run inference?
   - Use selection scores to weight probability distributions?
   - Combine multiple model predictions?

3. **What is the generation seed?**
   - User-provided seed for reproducibility?
   - Derived from selection fingerprint?
   - Timestamp-based?

4. **Do we need combination evaluation in MVP?**
   - Or just generation + persistence?
   - What criteria would we evaluate against?

### Secondary Questions
5. **Should F13 extend probability engine or create new module?**
6. **What is the maximum number of combinations per generation?**
7. **Should F13 support filtering (e.g., exclude historical draws)?**
8. **How does F13 handle insufficient selection data?**

## 13. Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Model artifact loading complexity | High | Start with probability-weighted generation (Option B) |
| Determinism across runs | Medium | Isolated RNG, fingerprint-based idempotency |
| Selection data insufficiency | Low | F12 ensures bounded output; fallback to defaults |
| Performance with large selections | Low | Bounded by top-K (max 20) |
| Scope creep (evaluation, filtering) | Medium | MVP: generation + persistence only |

---

## Gate Resolution (2026-08-11)

Decisions resolved from codebase/spec evidence before sdd-propose. Split into **confirmed** (backed by existing contract/code) and **requires authorization** (new decisions).

### Confirmed by codebase/spec
| # | Decision | Evidence |
|---|----------|----------|
| C1 | Combinations MUST respect lottery config: `numbers_to_select` distinct numbers in `[min_number, max_number]`, optional super number in `[super_number_min, super_number_max]`, numbers sorted | `lottery` model + CHECK constraints (`ck_lottery_min_max`, `ck_lottery_numbers_to_select`, `ck_lottery_super_range`) |
| C2 | F13 does NOT load/execute ML/DL artifacts. `meta_selection_entries` carries only `model_id`, `engine_type`, `rank`, `score` — no artifact references; no persisted artifacts for all engines | `meta_selection_entry.py` + F12 spec (META-006) |
| C3 | Determinism uses isolated `random.Random(seed)` derived from canonical SHA-256 of versioned inputs — reuse F5 `derive_seed`/`isolated_rng` | `probability/determinism.py` |
| C4 | MVP = generate + persist only. No evaluation tables exist; exploration recommends generation-only | codebase (no eval tables) + exploration §9 |
| C5 | No historical-draw exclusion, no extra statistical filters in MVP (no justification found) | exploration §6 + user gate rule 6 |
| C6 | Insufficient selection (no active F12 selection for lottery) → typed error, NO fallback generation, no engine execution | user gate rule 7 + boundary F12/F13 |
| C7 | Persistence follows F7-F12 snapshot pattern: immutable `gen_snapshots` header (lottery_id, selection_id FK, version, status, fingerprint, config_json, created_at) + `gen_combinations` entries (snapshot_id, position, numbers JSON, super_number, score, created_at); SHA-256 fingerprint idempotency; monotonic version per (lottery_id, selection_id) | F7-F12 snapshot pattern + exploration §8 Option 2 |
| C8 | Migration 0015 (additive, 2 new tables, no data migration), `generators/` module, `GenService`, 4 API endpoints + 4 CLI commands following F12 surface pattern | exploration §11 + F12 precedent |

### Requires authorization (new decisions)
| # | Decision | Proposal | Options |
|---|----------|----------|---------|
| N1 | Combination count per run: default + max configurable | Default 10, max 100, `count` param per request | Any default/max the user authorizes |
| N2 | How F12 scores map to generation weights | Score-weighted allocation: each selected model gets `round(score/total_score × count)` combinations; per-number probabilities come from existing F5 prob snapshot distributions (empirical/conditional), NOT from model inference. Selection determines WHICH probabilistic signals participate and their weight | (a) score-weighted allocation as proposed; (b) uniform allocation across selected models; (c) rank-only weighting |
| N3 | Seed policy | Default: seed derived from `(selection_fingerprint, lottery_id, count, GENERATOR_VERSION)` — reproducible; optional `seed` param overrides | (a) derived-only; (b) derived + optional override |
| N4 | New `generators/` module vs extending F5 probability engine | NEW `generators/` module reusing ONLY pure utilities (`derive_seed`, `isolated_rng`, `_canonical_json`). F5 `ProbabilityService` stays untouched (different concern: probability snapshot vs combination generation) | (a) new module as proposed; (b) extend probability engine |
| N5 | `gen_combinations.score` column | Include optional nullable `score` column (combination weight) | Include; exclude |

---
**Ready for sdd-propose ONLY after explicit authorization of N1–N5.**
