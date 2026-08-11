# Proposal: F11 — Experiment Engine

## Change Summary

| Field | Value |
|-------|-------|
| **Name** | `fase-11-experiment-engine` |
| **Goal** | Track, version, compare, and export experiment results across engine runs (F7/F8/F9/F10) |
| **Scope** | Registration, versioning, history, comparison, export (JSON/CSV) |
| **Boundaries** | No execution, no ranking, no UI, no new deps |

## Requirements

| ID | Description | Acceptance Criteria |
|----|-------------|---------------------|
| REQ-EXP-001 | Experiment CRUD — register, update, retire experiments scoped per lottery | `POST /experiment/create`, `GET /experiment/{id}`, `PATCH /experiment/{id}` return valid entities |
| REQ-EXP-002 | Version tracking — monotonic version per (lottery_id, name), SHA-256 fingerprint | Each mutation produces new version; fingerprint detects duplicates |
| REQ-EXP-EXP-003 | Run association — link engine snapshots via polymorphic `engine_snapshot_id` + `engine_type` | `POST /experiment/{id}/run` validates snapshot exists and type matches |
| REQ-EXP-004 | Experiment history — list/filter by lottery, status, date range | `GET /experiments` supports query params; returns ordered results |
| REQ-EXP-005 | Comparison — side-by-side metric comparison across runs within an experiment | `POST /experiment/{id}/compare` returns comparison matrix; persists snapshot |
| REQ-EXP-006 | Export — JSON and CSV export of experiment results and comparisons | `GET /experiment/{id}/export?format=json\|csv` returns correct format |
| REQ-EXP-007 | CLI — `lip exp create`, `lip exp list`, `lip exp compare`, `lip exp export` | All subcommands execute correctly with stdlib argparse |
| REQ-EXP-008 | Error taxonomy — `ExperimentError`, `ComparisonError` subclass `ServiceError` | Errors map to appropriate HTTP status codes |

## Architectural Decisions

| ID | Decision | Rationale | Approach |
|----|----------|-----------|----------|
| **D1** | Polymorphic `engine_snapshot_id` in `exp_runs` | Simpler schema; service validates references; DB FK not critical for tracking | Single `engine_snapshot_id` Integer + `engine_type` String CHECK constraint |
| **D2** | Persisted comparison snapshots | Snapshots immutable → comparisons never stale; fast reads, audit trail | Store in `exp_comparisons.comparison_json` |
| **D3** | Export in `exporters/experiment_exporter.py` | Respects existing `exporters/` seam; domain logic stays in `experiments/` | stdlib `json` + `csv`; no new deps |
| **D4** | 3-slice MVP | Incremental delivery; each slice independently testable | Slice 1: models+store; Slice 2: service+API+CLI; Slice 3: comparison+export |

## Entity Design

### `exp_experiments`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer PK | AUTOINCREMENT |
| `lottery_id` | Integer FK → `lottery.id` | RESTRICT |
| `name` | String(200) | NOT NULL |
| `description` | Text | NULLABLE |
| `status` | String(16) | CHECK `active\|retired\|failed` |
| `fingerprint` | String(64) | SHA-256 |
| `version` | String(32) | Monotonic per (lottery_id, name) |
| `config_json` | Text | NULLABLE |
| `created_at` | DateTime(tz) | NOT NULL |

**Unique**: `(lottery_id, name, fingerprint)`

### `exp_runs`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer PK | AUTOINCREMENT |
| `experiment_id` | Integer FK → `exp_experiments.id` | RESTRICT |
| `run_label` | String(100) | NOT NULL |
| `engine_type` | String(20) | CHECK `backtesting\|ml\|dl\|optimization` |
| `engine_snapshot_id` | Integer | NOT NULL (service validates FK) |
| `engine_fingerprint` | String(64) | Denormalized for fast lookup |
| `notes` | Text | NULLABLE |
| `created_at` | DateTime(tz) | NOT NULL |

### `exp_comparisons`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer PK | AUTOINCREMENT |
| `experiment_id` | Integer FK → `exp_experiments.id` | RESTRICT |
| `comparison_json` | Text | NOT NULL |
| `created_at` | DateTime(tz) | NOT NULL |

## Module Structure

| File | Action | Purpose |
|------|--------|---------|
| `experiments/types.py` | CREATE | Domain types: `ExperimentConfig`, `ComparisonResult` |
| `experiments/version.py` | CREATE | `EXPERIMENT_GENERATOR_VERSION` constant |
| `experiments/fingerprint.py` | CREATE | `compute_exp_fingerprint()` |
| `experiments/snapshot_store.py` | CREATE | `ExpSnapshotStore` — exp_* I/O |
| `experiments/engine.py` | CREATE | `ExperimentEngine` orchestrator |
| `models/exp_experiment.py` | CREATE | ORM model |
| `models/exp_run.py` | CREATE | ORM model |
| `models/exp_comparison.py` | CREATE | ORM model |
| `services/exp_service.py` | CREATE | `ExpService` composition root |
| `services/errors.py` | MODIFY | Add `ExperimentError`, `ComparisonError` |
| `api/v1/exp.py` | CREATE | API router |
| `api/v1/router.py` | MODIFY | Include `exp_router` |
| `api/errors.py` | MODIFY | Add error codes to `_CODE_TO_STATUS` |
| `cli.py` | MODIFY | Add `lip exp` subcommands |
| `exporters/experiment_exporter.py` | CREATE | JSON/CSV export (stdlib) |
| `models/__init__.py` | MODIFY | Re-export exp models for alembic |
| `alembic/versions/0013_exp_tables.py` | CREATE | Migration: exp_* tables |

## Slice Plan

| Slice | Scope | Est. LOC | Dependencies | Deliverables |
|-------|-------|----------|--------------|-------------|
| **S1** | Models + migration + types + fingerprint + version + store + tests | ~200 | None | `exp_experiments`, `exp_runs`, `exp_comparisons` tables; `ExpSnapshotStore`; unit tests |
| **S2** | Experiment engine + service + API + CLI + errors + tests | ~250 | S1 | `ExperimentEngine`; `ExpService`; `POST/GET/PATCH /experiment/*`; `lip exp`; `ExperimentError` |
| **S3** | Comparison + persistence + export JSON/CSV + tests | ~200 | S1+S2 | `ComparisonError`; `exp_comparisons` writes; export endpoints; comparison API |
| **Total** | | **~650** | | |

## Out of F11

| Concern | Owner | Why excluded |
|---------|-------|--------------|
| Backtest execution | F10 | Single-run execution belongs to F10 |
| ML/DL training | F7/F8 | Engines own training |
| Optimization | F9 | F9 owns optimization |
| Number generation | F13 | F13 owns generation |
| Dashboard/UI | F14 | F14 owns presentation |
| Auto-ranking/selection | F12 | F12 owns dynamic model selection |
| Overfitting detection | F12+ | Deferred to future phases |
| Scheduler/background jobs | — | No engine has scheduler |
| Metric computation | F7/F8/F9/F10 | Engines compute own metrics |
| Copying metrics/configs from other engines | — | F11 stores references only |

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Polymorphic FK breaks if engine adds new snapshot types | Low | Service validates `engine_type` against known set; extend CHECK constraint in migration |
| Comparison JSON becomes stale if referenced snapshots change | Low | Snapshots immutable by design; comparison computed at creation time |
| `exp_runs.engine_snapshot_id` has no DB-level FK | Medium | Service layer validates existence; add soft check in tests |
| Export format drift (JSON/CSV schema undocumented) | Low | Define canonical export schema in `types.py`; test round-trip |

## Rollback Plan

1. Reverse migration `0013`: `alembic downgrade -1` drops `exp_comparisons`, `exp_runs`, `exp_experiments`
2. Remove new files: `experiments/{types,version,fingerprint,snapshot_store,engine}.py`, `models/exp_*.py`, `services/exp_service.py`, `api/v1/exp.py`, `exporters/experiment_exporter.py`
3. Revert modifications: `models/__init__.py`, `services/errors.py`, `api/errors.py`, `api/v1/router.py`, `cli.py`
4. All changes are additive; no existing code is modified beyond imports/registrations

## Dependencies

- F10 Backtesting COMPLETE (snapshot tables exist)
- Migration head: 0012 (next = 0013)
- No new Python dependencies (stdlib `json` + `csv` only)
- Alembic for migration; SQLAlchemy ORM; FastAPI for API

## Success Criteria

- [ ] Migration 0013 creates all 3 tables with correct constraints
- [ ] `ExpSnapshotStore` CRUD operations pass unit tests
- [ ] `ExpService` registers, versions, and retrieves experiments
- [ ] API endpoints return correct HTTP codes and payloads
- [ ] `lip exp` CLI commands execute successfully
- [ ] Comparison produces correct metric matrix for 2+ runs
- [ ] Export produces valid JSON and CSV files
- [ ] Zero modifications to F10 backtesting code
- [ ] All tests pass via `backend/.venv/bin/pytest`

## Open Items

- Exact comparison metric schema (to be resolved in design phase)
- Cross-experiment comparison scope (MVP: within-experiment only)
- Future engine types beyond backtesting/ml/dl/optimization
