# Design: F11 — Experiment Engine

## Technical Approach

F11 adds a tracking/comparison layer over existing engines. It replicates the established snapshot lifecycle pattern (atomic upsert, monotonic version, SHA-256 fingerprint) for `exp_*` tables. Comparisons read metrics from referenced engine tables at query time and persist the result as an immutable JSON snapshot. Export uses stdlib `json`/`csv` via the existing `exporters/` seam. No engine execution — F11 only references snapshots by `(engine_type, engine_snapshot_id)`.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| **Polymorphic FK** | Single `engine_snapshot_id` + `engine_type` CHECK | Separate nullable FKs per engine | Simpler schema; service validates; extensible |
| **Comparison persistence** | Persist as JSON in `exp_comparisons` | Compute on-the-fly | Snapshots immutable → never stale; fast reads, audit trail |
| **Export location** | `exporters/experiment_exporter.py` | In `experiments/` | Respects existing seam; domain logic stays in engine |
| **Identity scope** | `(lottery_id, name)` natural key with versioning | UUID surrogate | Matches all existing engine patterns |

## Data Model

### Migration 0013

**`exp_experiments`**: `id` PK, `lottery_id` FK→lottery RESTRICT, `name` String(200), `description` Text nullable, `status` String(16) CHECK `active|retired|failed`, `fingerprint` String(64), `version` String(32), `config_json` Text nullable, `created_at` DateTime(tz). Unique `(lottery_id, name, fingerprint)`. Index `ix_exp_experiments_lottery_status` on `(lottery_id, status)`.

**`exp_runs`**: `id` PK, `experiment_id` FK→exp_experiments RESTRICT, `run_label` String(100), `engine_type` String(20) CHECK `backtesting|ml|dl|optimization`, `engine_snapshot_id` Integer NOT NULL, `engine_fingerprint` String(64) denormalized, `notes` Text nullable, `created_at` DateTime(tz). Index `ix_exp_runs_experiment`.

**`exp_comparisons`**: `id` PK, `experiment_id` FK→exp_experiments RESTRICT, `comparison_json` Text NOT NULL, `created_at` DateTime(tz). Index `ix_exp_comparisons_experiment`.

**Downgrade**: DROP `exp_comparisons`, `exp_runs`, `exp_experiments` in order.

## Module Structure

```
experiments/
  types.py              — ExperimentConfig, ComparisonResult dataclasses
  version.py            — EXPERIMENT_GENERATOR_VERSION = "1.0.0"
  fingerprint.py        — compute_exp_fingerprint(name, lottery_id, config_json, description, status)
  snapshot_store.py     — ExpSnapshotStore (CRUD, next_version, find_by_fingerprint, mark_failed)
  engine.py             — ExperimentEngine orchestrator (thin: delegates to store + service)
models/
  exp_experiment.py     — ExpExperiment ORM (mirrors BtSnapshot pattern)
  exp_run.py            — ExpRun ORM
  exp_comparison.py     — ExpComparison ORM
services/
  exp_service.py        — ExpService (composition root: create, update, retire, add_run, list, compare, export)
  errors.py             — Add ExperimentError, ComparisonError subclasses
api/v1/
  exp.py                — API router (7 endpoints)
  router.py             — Add exp_router include
  errors.py             — Add 7 error codes to _CODE_TO_STATUS
exporters/
  experiment_exporter.py — ExperimentExporter.export_json(), export_csv()
cli.py                  — Add lip exp subcommands (4)
```

## Snapshot Reference Pattern

`exp_runs.engine_snapshot_id` references different tables based on `engine_type`. No DB FK — service validates:

```python
ENGINE_TABLES = {
    "backtesting": "bt_snapshots",
    "ml": "ml_snapshots",
    "dl": "dl_snapshots",
    "optimization": "opt_snapshots",
}
```

Service validates via direct query to the target table using `session.get()`. Returns `SNAPSHOT_NOT_FOUND` (404) if missing, `SNAPSHOT_TYPE_MISMATCH` (422) if type doesn't match table.

## Lifecycle

- **active** → **retired**: PATCH status=retired; experiment becomes read-only
- **active** → **failed**: marked on unrecoverable error
- **Versioning**: monotonic `str(int(max) + 1)` per `(lottery_id, name)`
- **Fingerprint**: SHA-256 over `json.dumps({"name", "lottery_id", "config_json", "description", "status"}, sort_keys=True)`
- **Idempotency**: same `(lottery_id, name, fingerprint)` returns existing entity
- **Immutability**: retired experiments reject mutations; comparison snapshots never updated

## API Endpoints (7)

| Method | Path | Request | Response | Status | Errors |
|--------|------|---------|----------|--------|--------|
| POST | `/experiment/create` | `{lottery_id, name, description?, config_json?}` | `Experiment` | 200 | 409 DUPLICATE_EXPERIMENT |
| GET | `/experiment/{id}` | — | `Experiment` | 200 | 404 EXPERIMENT_NOT_FOUND |
| PATCH | `/experiment/{id}` | `{name?, description?, status?, config_json?}` | `Experiment` | 200 | 404, 409 EXPERIMENT_RETIRED |
| GET | `/experiments` | `?lottery_id&status&from&to` | `[Experiment]` | 200 | — |
| POST | `/experiment/{id}/run` | `{run_label, engine_type, engine_snapshot_id, notes?}` | `Run` | 200 | 404, 422 SNAPSHOT_TYPE_MISMATCH |
| POST | `/experiment/{id}/compare` | `{run_ids: [int]}` | `Comparison` | 200 | 422 COMPARISON_INSUFFICIENT_RUNS |
| GET | `/experiment/{id}/export` | `?format=json\|csv` | File | 200 | 422 EXPORT_FORMAT_INVALID |

## CLI Commands (4)

| Command | Arguments | Output |
|---------|-----------|--------|
| `lip exp create` | `--lottery-id`, `--name`, `[--description]` | JSON experiment |
| `lip exp list` | `--lottery-id`, `[--status]` | JSON array |
| `lip exp compare` | `--experiment-id`, `--run-ids` | JSON comparison |
| `lip exp export` | `--experiment-id`, `[--format json\|csv]` | JSON or CSV |

## Comparison System

**What**: Reads `aggregate_metrics_json` from `bt_results` (or `MlMetric`/`DlMetric`/`OptResult` per engine_type) for each referenced `engine_snapshot_id`. Builds a matrix keyed by `run_label` → `{metric_name: value}`.

**How**: For each run, service queries the referenced engine's result table. For backtesting: `BtResult.aggregate_metrics_json`. For ML/DL: `MlMetric`/`DlMetric` rows. For Opt: `OptResult`. Comparison computes no new metrics — it reads and formats.

**Determinism**: Same `(experiment_id, run_ids)` → identical `comparison_json`. Results sorted by `run_label` alphabetically.

**Result schema**:
```json
{
  "experiment_id": 1,
  "runs": [
    {
      "run_id": 10, "run_label": "baseline",
      "engine_type": "backtesting", "engine_snapshot_id": 5,
      "metrics": {"hit_rate": 0.12, "average_matches": 2.1, ...}
    }
  ],
  "metric_names": ["hit_rate", "average_matches", ...],
  "created_at": "2026-08-10T..."
}
```

Persisted in `exp_comparisons.comparison_json`. Idempotent: same run_ids → return cached.

## Export System

**JSON**: `{experiment: {...}, runs: [...], comparisons: [...]}`
**CSV**: columns `run_id, run_label, engine_type, engine_snapshot_id, engine_fingerprint, notes, created_at`

`ExperimentExporter` accepts `ExpService` data and writes to `StringIO`, returns content for API response or file for CLI.

## Error System

| Error Class | Code | HTTP | When |
|-------------|------|------|------|
| `ExperimentError` | `EXPERIMENT_NOT_FOUND` | 404 | Invalid experiment ID |
| `ExperimentError` | `EXPERIMENT_RETIRED` | 409 | Mutation on retired |
| `ExperimentError` | `DUPLICATE_EXPERIMENT` | 409 | Same fingerprint |
| `ExperimentError` | `SNAPSHOT_NOT_FOUND` | 404 | Invalid engine_snapshot_id |
| `ExperimentError` | `SNAPSHOT_TYPE_MISMATCH` | 422 | Type doesn't match table |
| `ComparisonError` | `COMPARISON_INSUFFICIENT_RUNS` | 422 | < 2 runs |
| `ExperimentError` | `EXPORT_FORMAT_INVALID` | 422 | Unsupported format |

## Sequence Diagrams

### Create Experiment
```
API/CLI → ExpService.create(lottery_id, name, config)
  → ExpSnapshotStore.next_version(lottery_id, name) → "1"
  → compute_exp_fingerprint(name, lottery_id, config, ...)
  → ExpSnapshotStore.find_by_fingerprint(fp) → None
  → session.add(ExpExperiment(status="active", version="1", fp))
  → session.commit()
  ← Experiment
```

### Register Run
```
API → ExpService.add_run(experiment_id, engine_type, snapshot_id)
  → session.get(ExpExperiment, experiment_id) → exp
  → Validate exp.status == "active"
  → Validate engine_type in ENGINE_TABLES
  → session.get(engine_table, snapshot_id) → snapshot
  → Copy snapshot.fingerprint → engine_fingerprint
  → session.add(ExpRun(...))
  → session.commit()
  ← Run
```

### Compare Runs
```
API → ExpService.compare(experiment_id, [run_ids])
  → Validate len(run_ids) >= 2
  → Query ExpRun for each run_id
  → For each run: query engine result table for metrics
  → Build comparison matrix (sorted by run_label)
  → session.add(ExpComparison(comparison_json=matrix))
  → session.commit()
  ← Comparison
```

### Export
```
API → ExpService.export(experiment_id, format)
  → Query ExpExperiment, ExpRun[], ExpComparison[]
  → ExperimentExporter.export_json(data) or export_csv(data)
  ← JSON string or CSV string
```

## Responsibility Boundaries

**F11 DOES NOT**: execute backtests (F10), run ML/DL training (F7/F8), run optimization (F9), generate numbers (F13), compute metrics (engines own this), rank/select models (F12), provide UI (F14), copy metrics into its tables.

**F11 DOES**: register experiments, version them, track run associations via references, compare results across runs, export data.

## Compatibility

- Replicates BtSnapshotStore pattern exactly (atomic upsert, monotonic version, SHA-256)
- Follows BtService service-layer pattern (session injection, private helpers)
- Matches bt.py API router pattern (Pydantic v2 schemas, SuccessEnvelope)
- CLI registration follows bt_parser pattern in cli.py
- Migration follows 0012 pattern (column definitions, portable DDL, additive only)
- Error taxonomy extends ServiceError like all other engines
- No imports of bt_*/ml_*/dl_*/opt_* at module level (service validates lazily)

## Performance

NFR: CRUD ≤ 50ms, export ≤ 200ms. Single-table queries with PK/index lookup. Comparison is O(n) reads from indexed tables. Export is in-memory string building. All within budget for SQLite at this scale.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No data migration. Migration 0013 is purely additive (3 new tables). Rollback: `alembic downgrade -1` drops the 3 tables. All changes are additive; no existing table modified.

## Open Questions

- [ ] None — all design decisions resolved per spec and proposal.
