# Spec — Experiment Engine (`experiment-engine`)

**Change**: `fase-11-experiment-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Artifact**: spec (this change) — new capability `experiment-engine`, parallel to `backtesting-engine` (F10), `opt-engine` (F9), `ml-engine` (F7), `dl-engine` (F8).

## Purpose

Track, version, compare, and export experiment results across engine runs (F7/F8/F9/F10). F11 does NOT execute engines or compute metrics — it stores references to engine snapshots, manages experiment lifecycle, and enables cross-run comparison and export. Every engine (backtesting, ML, DL, optimization) owns its own execution and metrics; F11 provides the orchestration layer for tracking what was tried and how it compared.

Engine requirements `EXP-001..008`; per-surface requirements `EXP-API-001..005`, `EXP-CLI-001..004`.

## Requirements Overview

| ID | Requirement | Priority | Cross-refs |
|----|-------------|----------|------------|
| EXP-001 | Experiment CRUD — register, update, retire per lottery | P0 | — |
| EXP-002 | Version tracking — monotonic version, SHA-256 fingerprint | P0 | — |
| EXP-003 | Run association — polymorphic engine_snapshot_id + engine_type | P0 | F10 bt_*, F7 ml_*, F8 dl_*, F9 opt_* |
| EXP-004 | Experiment history — list/filter by lottery, status, date range | P0 | — |
| EXP-005 | Comparison — side-by-side metric comparison across runs | P0 | — |
| EXP-006 | Export — JSON and CSV export of results and comparisons | P0 | — |
| EXP-007 | CLI — lip exp create/list/compare/export | P0 | — |
| EXP-008 | Error taxonomy — ExperimentError, ComparisonError subclass ServiceError | P0 | — |

## Requirements

### EXP-001: Experiment CRUD

The system SHALL support register, update, and retire operations on experiments scoped per lottery.

- `POST /experiment/create` — creates experiment, returns entity
- `GET /experiment/{id}` — returns experiment by ID
- `PATCH /experiment/{id}` — updates mutable fields (name, description, status, config_json)
- Status transitions: `active` → `retired` or `active` → `failed`. Retired experiments are read-only.
- `lottery_id` is immutable after creation.

**Entities touched**: `exp_experiments`

#### Scenario: create experiment
- GIVEN a valid lottery_id and experiment name
- WHEN POST /experiment/create is called
- THEN experiment is created with status=active, version=1, and fingerprint computed

#### Scenario: update experiment
- GIVEN an active experiment with id=X
- WHEN PATCH /experiment/{X} updates description
- THEN description is updated, version increments, fingerprint recomputed

#### Scenario: retire experiment
- GIVEN an active experiment
- WHEN PATCH sets status=retired
- THEN experiment becomes read-only; further mutations are rejected

#### Scenario: duplicate name within lottery
- GIVEN an experiment with (lottery_id=L, name=N) already exists
- WHEN creating another with same (L, N) and same fingerprint
- THEN the existing experiment is returned (idempotent)

### EXP-002: Version Tracking

The system SHALL assign a monotonic version per `(lottery_id, name)` pair. Each mutation produces a new version. The system SHALL compute a SHA-256 fingerprint over `(lottery_id, name, config_json, description, status)`. Fingerprint enables duplicate detection: same fingerprint = same content, skip write.

**Entities touched**: `exp_experiments.version`, `exp_experiments.fingerprint`

#### Scenario: version increments on mutation
- GIVEN experiment with version=3
- WHEN any mutable field changes
- THEN version becomes 4 and fingerprint changes

#### Scenario: fingerprint detects duplicate
- GIVEN experiment with fingerprint=X
- WHEN same mutation is applied again
- THEN version and fingerprint remain unchanged (idempotent)

#### Scenario: different config produces different fingerprint
- GIVEN two experiments with same name but different config_json
- WHEN both are created
- THEN their fingerprints differ

### EXP-003: Run Association

The system SHALL link engine snapshots to experiments via polymorphic `engine_snapshot_id` (Integer) + `engine_type` (String CHECK: `backtesting|ml|dl|optimization`). The service layer MUST validate that the referenced snapshot exists in the corresponding engine's table (`bt_snapshots`, `ml_snapshots`, `dl_snapshots`, `opt_snapshots`). No DB-level FK — validation is service responsibility.

Cross-references: F10 `bt_snapshots`, F7 `ml_snapshots`, F8 `dl_snapshots`, F9 `opt_snapshots`.

**Entities touched**: `exp_runs`

#### Scenario: valid run association
- GIVEN an active experiment and a backtest snapshot in bt_snapshots
- WHEN POST /experiment/{id}/run with engine_type=backtesting, engine_snapshot_id=S
- THEN run is created with engine_fingerprint copied from snapshot

#### Scenario: invalid snapshot reference
- GIVEN engine_type=ml but snapshot_id references a bt_snapshots row
- WHEN POST /experiment/{id}/run is called
- THEN validation error is returned; no row written

#### Scenario: missing snapshot
- GIVEN engine_snapshot_id references a non-existent row
- WHEN POST /experiment/{id}/run is called
- THEN 404 RESOURCE_NOT_FOUND error

### EXP-004: Experiment History

The system SHALL list and filter experiments by lottery_id, status, and date range. Results SHALL be ordered by `created_at DESC`.

**Entities touched**: `exp_experiments`

#### Scenario: list by lottery
- GIVEN experiments across 3 lotteries
- WHEN GET /experiments?lottery_id=L is called
- THEN only experiments for lottery L are returned

#### Scenario: filter by status and date
- GIVEN experiments with various statuses and dates
- WHEN GET /experiments?status=active&from=2026-01-01&to=2026-06-30
- THEN only active experiments within the date range are returned

#### Scenario: empty result
- GIVEN no experiments for a lottery
- WHEN GET /experiments?lottery_id=999
- THEN empty list is returned with success=true

### EXP-005: Comparison

The system SHALL compute side-by-side metric comparison across 2+ runs within an experiment. The comparison SHALL be persisted as an immutable snapshot in `exp_comparisons.comparison_json`. Comparisons are within-experiment only (no cross-experiment comparison in MVP).

**Entities touched**: `exp_comparisons`

#### Scenario: compare two runs
- GIVEN an experiment with 2 runs (R1, R2) referencing bt_snapshots
- WHEN POST /experiment/{id}/compare with run_ids=[R1, R2]
- THEN comparison matrix is returned and persisted

#### Scenario: insufficient runs
- GIVEN an experiment with 1 run
- WHEN POST /experiment/{id}/compare with 1 run
- THEN validation error: at least 2 runs required

#### Scenario: comparison idempotent
- GIVEN a persisted comparison for run_ids=[R1, R2]
- WHEN same comparison is requested again
- THEN existing comparison is returned without recomputation

### EXP-006: Export

The system SHALL export experiment results and comparisons in JSON and CSV formats.

- `GET /experiment/{id}/export?format=json` — returns structured JSON
- `GET /experiment/{id}/export?format=csv` — returns CSV with header row
- Export includes: experiment metadata, all runs, all comparisons

**Entities touched**: `exp_experiments`, `exp_runs`, `exp_comparisons`

#### Scenario: JSON export
- GIVEN an experiment with 3 runs and 1 comparison
- WHEN GET /experiment/{id}/export?format=json
- THEN valid JSON with experiment, runs array, and comparisons array

#### Scenario: CSV export
- GIVEN an experiment with 3 runs
- WHEN GET /experiment/{id}/export?format=csv
- THEN CSV with columns: run_id, run_label, engine_type, engine_snapshot_id, engine_fingerprint, notes, created_at

#### Scenario: invalid format
- GIVEN an experiment
- WHEN GET /experiment/{id}/export?format=xml
- THEN 422 VALIDATION_ERROR with supported formats

### EXP-007: CLI

The CLI SHALL expose `lip exp` subcommands using stdlib argparse:

- `lip exp create --lottery-id <id> --name <name> [--description <desc>]`
- `lip exp list --lottery-id <id> [--status <status>]`
- `lip exp compare --experiment-id <id> --run-ids <id1,id2>`
- `lip exp export --experiment-id <id> [--format json|csv]`

All subcommands produce JSON output. Behavior matches API.

#### Scenario: create via CLI
- WHEN `lip exp create --lottery-id 1 --name "Test"`
- THEN experiment is created and JSON response printed

#### Scenario: list via CLI
- WHEN `lip exp list --lottery-id 1 --status active`
- THEN filtered experiments returned as JSON array

### EXP-008: Error Taxonomy

The system SHALL define `ExperimentError` and `ComparisonError` as subclasses of `ServiceError`. Error codes map to HTTP status codes in `api/errors.py`.

| Error | HTTP Status | When |
|-------|-------------|------|
| EXPERIMENT_NOT_FOUND | 404 | Invalid experiment ID |
| EXPERIMENT_RETIRED | 409 | Mutation on retired experiment |
| DUPLICATE_EXPERIMENT | 409 | Same (lottery_id, name, fingerprint) |
| SNAPSHOT_NOT_FOUND | 404 | Invalid engine_snapshot_id |
| SNAPSHOT_TYPE_MISMATCH | 422 | engine_type doesn't match snapshot table |
| COMPARISON_INSUFFICIENT_RUNS | 422 | Less than 2 runs for comparison |
| EXPORT_FORMAT_INVALID | 422 | Unsupported export format |

## Migration 0013: `exp_*` Tables

Migration creates `exp_experiments`, `exp_runs`, `exp_comparisons` tables. Additive only — no existing table modified.

### `exp_experiments`

| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| lottery_id | Integer FK → lottery.id | RESTRICT, NOT NULL |
| name | String(200) | NOT NULL |
| description | Text | NULLABLE |
| status | String(16) | CHECK active\|retired\|failed, NOT NULL |
| fingerprint | String(64) | SHA-256, NOT NULL |
| version | String(32) | NOT NULL |
| config_json | Text | NULLABLE |
| created_at | DateTime(tz) | NOT NULL |

**Unique**: `(lottery_id, name, fingerprint)`
**Index**: `ix_exp_experiments_lottery_status` on `(lottery_id, status)`

### `exp_runs`

| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| experiment_id | Integer FK → exp_experiments.id | RESTRICT, NOT NULL |
| run_label | String(100) | NOT NULL |
| engine_type | String(20) | CHECK backtesting\|ml\|dl\|optimization, NOT NULL |
| engine_snapshot_id | Integer | NOT NULL (service validates FK) |
| engine_fingerprint | String(64) | NOT NULL |
| notes | Text | NULLABLE |
| created_at | DateTime(tz) | NOT NULL |

**Index**: `ix_exp_runs_experiment` on `(experiment_id)`

### `exp_comparisons`

| Column | Type | Constraints |
|--------|------|-------------|
| id | Integer PK | AUTOINCREMENT |
| experiment_id | Integer FK → exp_experiments.id | RESTRICT, NOT NULL |
| comparison_json | Text | NOT NULL |
| created_at | DateTime(tz) | NOT NULL |

**Index**: `ix_exp_comparisons_experiment` on `(experiment_id)`

**Downgrade**: DROP `exp_comparisons`, `exp_runs`, `exp_experiments` in order.

## API Endpoints

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | /experiment/create | `{lottery_id, name, description?, config_json?}` | `{success, data: Experiment}` | 409 DUPLICATE |
| GET | /experiment/{id} | — | `{success, data: Experiment}` | 404 |
| PATCH | /experiment/{id} | `{name?, description?, status?, config_json?}` | `{success, data: Experiment}` | 404, 409 RETIRED |
| GET | /experiments | `?lottery_id&status&from&to` | `{success, data: [Experiment]}` | — |
| POST | /experiment/{id}/run | `{run_label, engine_type, engine_snapshot_id, notes?}` | `{success, data: Run}` | 404, 422 |
| POST | /experiment/{id}/compare | `{run_ids: [int]}` | `{success, data: Comparison}` | 422 |
| GET | /experiment/{id}/export | `?format=json\|csv` | File response | 422 |

All responses use standard envelope: `{success, data|error, timestamp}`.

## CLI Commands

| Command | Args | Output |
|---------|------|--------|
| lip exp create | --lottery-id, --name, [--description] | JSON experiment |
| lip exp list | --lottery-id, [--status] | JSON array |
| lip exp compare | --experiment-id, --run-ids | JSON comparison |
| lip exp export | --experiment-id, [--format] | JSON or CSV file |

## Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-EXP-01 | Performance | Experiment CRUD ≤ 50ms p95; export ≤ 200ms p95 |
| NFR-EXP-02 | Determinism | Same inputs → identical fingerprint; comparison matrix deterministic |
| NFR-EXP-03 | Idempotency | Same (lottery_id, name, fingerprint) returns existing; same comparison returns cached |
| NFR-EXP-04 | Immutability | Comparison snapshots never mutated; experiments only transition status |
| NFR-EXP-05 | Isolation | Experiments scoped per lottery; no cross-lottery contamination |
| NFR-EXP-06 | Error handling | All errors subclass ServiceError; map to correct HTTP codes |
| NFR-EXP-07 | Rollback | Migration 0013 downgrade drops only exp_* tables; no existing table modified |
| NFR-EXP-08 | No new deps | stdlib json + csv only; no external packages |
| NFR-EXP-09 | Engine boundary | F11 does NOT import bt_*, ml_*, dl_*, opt_* at module level; service validates references |

## Traceability: Proposal → Requirements

| Proposal | Requirements |
|----------|--------------|
| REQ-EXP-001 | EXP-001 |
| REQ-EXP-002 | EXP-002 |
| REQ-EXP-003 | EXP-003 |
| REQ-EXP-004 | EXP-004 |
| REQ-EXP-005 | EXP-005 |
| REQ-EXP-006 | EXP-006 |
| REQ-EXP-007 | EXP-007 |
| REQ-EXP-008 | EXP-008 |
| Migration 0013 | Migration section |
| API endpoints | API Endpoints section |
| CLI commands | CLI Commands section |

## Conflicts or Ambiguities

None discovered. All requirements consistent with proposal decisions D1-D4.

---

**Ready for design (sdd-design) upon confirmation.**
