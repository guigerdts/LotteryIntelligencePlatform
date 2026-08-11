# Exploration — Experiment Engine (`fase-11-experiment-engine`)

**Change**: `fase-11-experiment-engine` · **Store**: `hybrid` (openspec + engram)
**Date**: 2026-08-10 · **Phase**: sdd-explore

## 1. Findings

### 1.1 No existing experiment implementation

The `experiments/` package exists as a **seam-only placeholder** since Fase 0:

```
backend/src/backend/app/experiments/__init__.py  →  """Experiment orchestration engine (Fase 11)."""
```

Zero logic, zero models, zero tables, zero tests. No `exp_*` ORM models, no migration, no API endpoints, no CLI commands. The package is registered in the package tree and imported by `models/__init__.py` — but nothing beyond a docstring.

### 1.2 Roadmap scope (authoritative)

`IMPLEMENTATION_ROADMAP.md` §Fase 11 defines five capabilities:

| Capability | Spanish |
|------------|---------|
| Experiment registration | Registro |
| Versioning | Versionado |
| History | Historial |
| Comparison | Comparación |
| Results export | Exportación |

The dependency chain is: F10 (Backtesting) → **F11** → F12 (Meta Learning) → F13 (Generator).

### 1.3 F10 Backtesting outputs (F11's primary inputs)

F10 is COMPLETE and archived. Its output artifacts are:

| Artifact | Shape | File |
|----------|-------|------|
| `BtSnapshot` | `id`, `lottery_id`, `strategy_id`, `fingerprint`, `version`, `status`, `config_json`, `created_at` | `models/bt_snapshot.py` |
| `BtResult` | `snapshot_id`, `aggregate_metrics_json`, `window_history_json` | `models/bt_result.py` |
| `BtRunOutcome` | `snapshot_id`, `lottery_id`, `strategy_id`, `fingerprint`, `version`, `status` | `services/bt_service.py` |
| `BtHistoryEntry` | snapshot_id + metadata + `created_at` | `services/bt_service.py` |
| Metrics shape | `{hit_rate, average_matches, consistency_score, total_draws_evaluated}` (Decimal) | `backtesting/metrics.py` |

### 1.4 Other engine outputs (potential F11 consumers)

| Engine | Snapshot Model | Key Fields | File |
|--------|---------------|------------|------|
| ML (F7) | `MlSnapshot` | `ml_id`, `family`, `fingerprint`, `version`, `status` | `models/ml_snapshot.py` |
| ML (F7) | `MlMetric` | `snapshot_id`, `model_id`, `metric_type`, `metric_value` | `models/ml_metric.py` |
| DL (F8) | `DlSnapshot` | `dl_id`, `model_type`, `fingerprint`, `version`, `status` | `models/dl_snapshot.py` |
| DL (F8) | `DlMetric` | `snapshot_id`, `model_id`, `metric_type`, `metric_value` | `models/dl_metric.py` |
| Opt (F9) | `OptSnapshot` | `optimizer`, `fingerprint`, `version`, `status`, `objective_metric` | `models/opt_snapshot.py` |
| Opt (F9) | `OptResult` | `snapshot_id`, best params, convergence | `models/opt_result.py` |

### 1.5 Established infrastructure patterns

| Pattern | Reference | F11 reuse |
|---------|-----------|-----------|
| `engine_version` constant | `backtesting/version.py` → `BACKTEST_GENERATOR_VERSION = "1.0.0"` | Create `EXPERIMENT_GENERATOR_VERSION` |
| SHA-256 fingerprint | `backtesting/fingerprint.py` → `compute_bt_fingerprint()` | Create `compute_exp_fingerprint()` |
| Atomic upsert (delete+insert) | `backtesting/snapshot_store.py` → `BtSnapshotStore.create_active()` | Reuse pattern for `ExpSnapshotStore` |
| Monotonic version | `backtesting/snapshot_store.py` → `next_version()` | Reuse pattern |
| Service layer | `services/bt_service.py` → `BtService` | Create `ExpService` |
| API router | `api/v1/bt.py` → `router = APIRouter(prefix="/backtesting")` | Create `api/v1/exp.py` |
| CLI registration | `cli.py` → `bt_parser = subparsers.add_parser("bt")` | Add `lip exp` subcommands |
| Error taxonomy | `services/errors.py` → custom `ServiceError` subclasses | Add `ExperimentError`, `ComparisonError` |
| API error mapping | `api/errors.py` → `_CODE_TO_STATUS` dict | Add new codes |
| Migration pattern | `alembic/versions/0012_bt_tables.py` | Next = `0013_exp_tables.py` |
| Router registration | `api/v1/router.py` → `api_v1_router.include_router(bt_router)` | Add `exp_router` |
| `models/__init__.py` re-exports | Required for alembic `target_metadata` | Add exp models |
| JSON columns for payloads | `bt_results.aggregate_metrics_json`, `.window_history_json` | Same pattern for experiment results |

### 1.6 Boundary analysis: F10 vs F11

From the F10 design (§23):

| Concern | F10 Backtesting | F11 Experiment |
|---------|-----------------|----------------|
| Goal | Evaluate a strategy historically | Track/compare runs across experiments |
| Input | Strategy + historical data | Experiment definitions (references to snapshots) |
| Output | Single-run results | Cross-run comparison, versioned experiment history |
| API | `POST /backtesting/run` | `POST /experiment/create` |
| CLI | `lip bt ...` | `lip exp ...` |

**Critical rule**: F10 produces single-run results. F11 tracks and compares across runs. Ranking **within** a single backtest is F10; **cross-run** ranking is F11.

### 1.7 Dependencies available (pyproject.toml)

Current runtime deps: `alembic`, `fastapi`, `httpx`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `uvicorn`, `numpy`, `scikit-learn`, `torch`, `deap`, `optuna`. **No pandas, no csv stdlib constraint** — stdlib `json` and `csv` are available for export. No new deps needed for F11.

## 2. Current State

| Area | State | Path |
|------|-------|------|
| `experiments/__init__.py` | Seam-only placeholder (docstring) | `backend/src/backend/app/experiments/__init__.py` |
| `exp_*` models | **None** | — |
| `exp_*` migration | **None** (next = `0013`) | `backend/alembic/versions/` |
| `ExpService` | **None** | — |
| `ExpSnapshotStore` | **None** | — |
| `api/v1/exp.py` | **None** | — |
| CLI `lip exp` | **None** | `backend/src/backend/app/cli.py` |
| Export layer | Seam-only placeholder (docstring) | `backend/src/backend/app/exporters/__init__.py` |
| F10 Backtesting | COMPLETE, archived | `openspec/changes/archive/2026-08-10-fase-10-backtesting-engine/` |

## 3. Reusable Capabilities

### 3.1 Snapshot lifecycle pattern (all engines)

Every engine follows the same snapshot pattern:
- **Header table**: `*_snapshots` with `id`, `lottery_id`, `fingerprint`, `version`, `status` (`active|retired|failed`), `config_json`, `created_at`
- **Payload table**: `*_results` or `*_metrics` with FK to snapshot header + JSON payloads
- **Store class**: atomic upsert via delete-old + insert-new in single transaction
- **Version**: monotonic integer-as-string per scope
- **Fingerprint**: SHA-256 of inputs for idempotent re-execution detection

F11 should replicate this pattern exactly with `exp_*` tables.

### 3.2 BtSnapshotStore.create_active() pattern

```python
# 1. Delete existing rows with same fingerprint
# 2. Create new snapshot with status='active'
# 3. Create result with metrics
# 4. Flush
```

### 3.3 Error taxonomy extension

```python
class ExperimentError(ServiceError):
    code = "EXPERIMENT_ERROR"

class ComparisonError(ServiceError):
    code = "COMPARISON_ERROR"
```

Register in `api/errors.py` `_CODE_TO_STATUS`.

### 3.4 Version/fingerprint constants

```python
EXPERIMENT_GENERATOR_VERSION: Final[str] = "1.0.0"
```

### 3.5 CLI registration pattern

```python
exp_parser = subparsers.add_parser("exp", help="...")
exp_sub = exp_parser.add_subparsers(dest="exp_command", required=True)
```

### 3.6 Export pattern

`exporters/__init__.py` is a seam. F11 can implement CSV/JSON export using stdlib (`json`, `csv` modules) — no new deps needed.

## 4. F11 Boundaries

### What F11 DOES

- **Register** an experiment: a named, versioned container that references one or more engine snapshots (bt_*, ml_*, dl_*, opt_*)
- **Version** experiments: each modification creates a new version; history is preserved
- **Track history**: list all experiments, filter by lottery/strategy/status
- **Compare** results across experiments: side-by-side metric comparison of referenced snapshots
- **Export** experiment results to JSON/CSV

### What F11 DOES NOT do (stays in other engines)

| Concern | Stays in | Why |
|---------|----------|-----|
| Running backtests | F10 Backtesting | F10 owns single-run execution |
| Running ML/DL training | F7/F8 | F7/F8 own training |
| Running optimization | F9 | F9 owns optimization |
| Number generation | F13 Generator | F13 owns generation |
| Dashboard/UI | F14 Dashboard | F14 owns presentation |
| Auto-ranking/selection | F12 Meta Learning | F12 owns dynamic model selection |
| Strategy evaluation logic | F10 | F10 owns walk-forward evaluation |
| Metric computation | F10/F7/F8/F9 | Engines compute their own metrics |

### Non-duplication rule

F11 references snapshot IDs from other engines. It **never** copies metrics, configs, or results into its own tables — it stores only the references (`bt_snapshot_id`, `ml_snapshot_id`, etc.) and any experiment-specific metadata (name, description, tags, notes). Comparison reads from the referenced engine tables at query time.

## 5. Proposed Entities & Persistence

### 5.1 `exp_experiments` (experiment registry)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Auto-increment |
| `lottery_id` | Integer FK → `lottery.id` RESTRICT | Scoped per lottery |
| `name` | String(200) | Human-readable experiment name |
| `description` | Text | Optional description |
| `status` | String(16) CHECK `active|retired|failed` | Lifecycle |
| `fingerprint` | String(64) | SHA-256 of (name + lottery_id + config) |
| `version` | String(32) | Monotonic per (lottery_id, name) |
| `config_json` | Text | Experiment-level config (tags, notes, parameters) |
| `created_at` | DateTime(tz) | Creation timestamp |

**Unique constraint**: `(lottery_id, name, fingerprint)` — one fingerprint per (lottery, name).

### 5.2 `exp_runs` (experiment runs — references to engine snapshots)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Auto-increment |
| `experiment_id` | Integer FK → `exp_experiments.id` RESTRICT | Parent experiment |
| `run_label` | String(100) | Human label for this run (e.g. "baseline", "v2-tuned") |
| `engine_type` | String(20) CHECK `backtesting|ml|dl|optimization` | Which engine produced this |
| `engine_snapshot_id` | Integer | FK to the engine's snapshot table (polymorphic reference) |
| `engine_fingerprint` | String(64) | The snapshot's fingerprint (denormalized for fast lookup) |
| `notes` | Text | Run-specific notes |
| `created_at` | DateTime(tz) | |

**Design decision**: `engine_snapshot_id` is intentionally NOT a hard FK to a specific table because it references different tables depending on `engine_type`. The service layer validates the reference exists. An alternative is separate nullable FK columns (`bt_snapshot_id`, `ml_snapshot_id`, etc.) — see §7.

### 5.3 `exp_comparisons` (comparison snapshots)

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Auto-increment |
| `experiment_id` | Integer FK → `exp_experiments.id` RESTRICT | |
| `comparison_json` | Text | Serialized comparison result (metric table) |
| `created_at` | DateTime(tz) | |

### 5.4 Migration

`0013_exp_tables.py` — creates `exp_experiments`, `exp_runs`, `exp_comparisons` + indexes. Additive only, no touches to bt_*/ml_*/dl_*/opt_*.

### 5.5 Module structure

```
backend/src/backend/app/experiments/
├── __init__.py              # Package seam (docstring only)
├── types.py                 # ExperimentConfig, ExperimentResult, ComparisonResult
├── fingerprint.py           # SHA-256 fingerprint computation
├── version.py               # EXPERIMENT_GENERATOR_VERSION constant
├── snapshot_store.py        # ExpSnapshotStore — exp_* I/O owner
└── engine.py                # ExperimentEngine orchestrator

backend/src/backend/app/models/
├── exp_experiment.py        # ExpExperiment ORM model
├── exp_run.py               # ExpRun ORM model
└── exp_comparison.py        # ExpComparison ORM model

backend/src/backend/app/services/
├── exp_service.py           # ExpService composition root

backend/src/backend/app/api/v1/
├── exp.py                   # API router

cli.py                       # Add lip exp subcommands
```

## 6. Open Questions

### Q1: Polymorphic reference vs separate FK columns for `exp_runs.engine_snapshot_id`

**Option A** (polymorphic): Single `engine_snapshot_id` Integer + `engine_type` String. Service validates reference. Simpler schema, but no DB-level FK constraint.

**Option B** (separate FKs): `bt_snapshot_id`, `ml_snapshot_id`, `dl_snapshot_id`, `opt_snapshot_id` as nullable FKs. DB enforces referential integrity. More columns, but safer.

**Recommendation**: Option A for F11 v1. The service layer validates; DB-level FK is nice-to-have but not critical for a tracking system. Option B can be added later if needed.

### Q2: Experiment naming/identity

Should experiments be identified by:
- `(lottery_id, name)` as natural key with versioning?
- Or a UUID/surrogate key with `name` as display-only?

The existing pattern uses `(lottery_id, strategy_id)` or `(lottery_id, optimizer)` as scope. For experiments, `(lottery_id, name)` makes sense as the logical scope.

### Q3: Comparison scope

Should comparison be:
- Within a single experiment (compare runs within one experiment)?
- Across experiments (compare Experiment A vs Experiment B)?
- Both?

The roadmap says "Comparación" — likely both, but the MVP should focus on within-experiment comparison first.

### Q4: Export formats

- JSON (trivial, matches existing patterns)
- CSV (stdlib `csv` module, no deps needed)
- Both in v1?

### Q5: Relationship to F12 Meta Learning

F12 is described as "evaluate historical model performance and dynamically select most promising models." F11 provides the data (experiment history, comparison results) that F12 consumes. The boundary is: F11 tracks and compares, F12 decides and selects.

## 7. Decisions Needing Authorization

### D1: Entity design — polymorphic vs multi-FK

**Question**: Should `exp_runs` use a single `engine_snapshot_id` (Option A) or separate FK columns per engine type (Option B)?

**Recommendation**: Option A (polymorphic) for simplicity. The service validates references.

### D2: Comparison persistence

**Question**: Should comparisons be persisted as snapshots (`exp_comparisons` table) or computed on-the-fly?

**Option A**: Persist comparison results as JSON in `exp_comparisons`. Pro: fast reads, audit trail. Con: stale if referenced snapshots change (but snapshots are immutable, so this is unlikely).

**Option B**: Compute on-the-fly from referenced snapshots. Pro: always current. Con: slower reads, no audit trail.

**Recommendation**: Option A (persist). Snapshots are immutable, so comparisons never go stale.

### D3: Export implementation location

**Question**: Should export be in `experiments/` engine module or in the existing `exporters/` seam?

**Recommendation**: `exporters/` is the project-wide export layer (F2 seam). F11 should implement experiment export in `exporters/experiment_exporter.py` (or similar) and expose it through the service/API. The `experiments/` engine stays focused on domain logic.

### D4: MVP scope

**Question**: What's the minimum viable slice for F11?

**Recommendation**:
- Slice 1: Entity models + migration + basic CRUD (register experiment, add run)
- Slice 2: Comparison logic + API/CLI
- Slice 3: Export (JSON + CSV)

## 8. Initial Scope Proposal

### Slice 1: Experiment Registry + Persistence (~200 lines)

**Files created**:
- `backend/src/backend/app/experiments/types.py`
- `backend/src/backend/app/experiments/version.py`
- `backend/src/backend/app/experiments/fingerprint.py`
- `backend/src/backend/app/experiments/snapshot_store.py`
- `backend/src/backend/app/models/exp_experiment.py`
- `backend/src/backend/app/models/exp_run.py`
- `backend/src/backend/app/models/exp_comparison.py`
- `backend/alembic/versions/0013_exp_tables.py`
- `tests/test_exp_pr1.py` (models + migration + store)

**Files modified**:
- `backend/src/backend/app/models/__init__.py` (add re-exports)
- `backend/src/backend/app/experiments/__init__.py` (docstring update)

### Slice 2: Service + API + CLI (~250 lines)

**Files created**:
- `backend/src/backend/app/experiments/engine.py`
- `backend/src/backend/app/services/exp_service.py`
- `backend/src/backend/app/api/v1/exp.py`
- `tests/test_exp_service.py`
- `tests/test_exp_api.py`

**Files modified**:
- `backend/src/backend/app/cli.py` (add `lip exp` subcommands)
- `backend/src/backend/app/api/v1/router.py` (include `exp_router`)
- `backend/src/backend/app/services/errors.py` (add `ExperimentError`)
- `backend/src/backend/app/api/errors.py` (add error codes)

### Slice 3: Comparison + Export (~200 lines)

**Files created**:
- `backend/src/backend/app/exporters/experiment_exporter.py`
- `tests/test_exp_comparison.py`
- `tests/test_exp_export.py`

**Files modified**:
- `backend/src/backend/app/services/exp_service.py` (add comparison + export methods)
- `backend/src/backend/app/api/v1/exp.py` (add comparison + export endpoints)

### Total estimated: ~650 lines across 3 slices

## 9. Explicitly OUT of F11

| Concern | Owner | Why it's excluded |
|---------|-------|-------------------|
| Backtest execution | F10 | F10 owns single-run backtest |
| ML/DL training | F7/F8 | Engines own training |
| Optimization | F9 | F9 owns optimization |
| Number generation | F13 | F13 owns generation |
| Dashboard/UI | F14 | F14 owns presentation |
| Auto-ranking/selection | F12 | F12 owns dynamic model selection |
| Strategy evaluation logic | F10 | F10 owns walk-forward |
| Metric computation | F7/F8/F9/F10 | Engines compute metrics |
| Scheduler/auto-execution | None | No engine has a scheduler |
| Feature engineering | F4 | F4 owns features |
| Statistics generation | F3 | F3 owns statistics |
| Probability computation | F5 | F5 owns probability |
| Graph computation | F6 | F6 owns graphs |
| Data import | F2 | F2 owns import |
| Overfitting detection | F11? | Defer to F12 or future — F11 tracks results only |

## Key Learnings

1. The `experiments/` package has been a seam placeholder since Fase 0 with zero implementation.
2. F10 Backtesting outputs `bt_snapshots` + `bt_results` with JSON payloads — F11 should reference these by snapshot_id, not copy data.
3. The project follows a strict snapshot lifecycle pattern (active/retired/failed, atomic upsert, monotonic version, SHA-256 fingerprint) that F11 should replicate exactly.
4. Migration `0013` is the next available number; all prior migrations (0001-0012) are complete.
5. No new dependencies are needed — stdlib `json` and `csv` suffice for export.
