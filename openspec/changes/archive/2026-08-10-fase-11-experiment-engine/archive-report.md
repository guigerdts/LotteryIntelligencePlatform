# Archive Report — Fase 11: Experiment Engine

**Change**: `fase-11-experiment-engine`
**Store**: `openspec`
**Archived**: `2026-08-10`
**Archived to**: `openspec/changes/archive/2026-08-10-fase-11-experiment-engine/`

## Purpose

Tracking/comparison layer over existing engines (F7/F8/F9/F10). Registers experiments, versions them, tracks run associations via polymorphic snapshot references, compares results across runs, and exports to JSON/CSV. Does NOT execute engines or compute metrics — stores references only.

## Scope

- **In scope**: Experiment registration, versioning, history, comparison (within-experiment), export (JSON/CSV), polymorphic snapshot references, 7 API endpoints, 4 CLI commands
- **Out of scope**: F12 (ranking/selection), F13 (generation), F14 (dashboard), engine execution, metric computation, auto-execution

## Final State

### Commits on Main (PR1–PR3)

| PR | Hash | Description |
|----|------|-------------|
| PR1 | `d712e00` | Foundation — migration 0013, ORM models, types, fingerprint, store |
| PR2 | `5cc2cf4` | Engine + Surface — service, API (5 endpoints), CLI (2 commands), errors |
| PR3 | `dcdd8e6` | Comparison + Export — comparison logic, export JSON/CSV, full surface |

### Requirements EXP-001..008

| ID | Requirement | PR |
|----|-------------|----|
| EXP-001 | Experiment CRUD | PR1+PR2 |
| EXP-002 | Version tracking | PR1 |
| EXP-003 | Run association (polymorphic) | PR1+PR2 |
| EXP-004 | Experiment history | PR2 |
| EXP-005 | Comparison | PR3 |
| EXP-006 | Export JSON/CSV | PR3 |
| EXP-007 | CLI | PR2+PR3 |
| EXP-008 | Error taxonomy | PR2 |

### Requirements NFR-EXP-01..09

| ID | Category | Status |
|----|----------|--------|
| NFR-EXP-01 | Performance | ✅ |
| NFR-EXP-02 | Determinism | ✅ |
| NFR-EXP-03 | Idempotency | ✅ |
| NFR-EXP-04 | Immutability | ✅ |
| NFR-EXP-05 | Isolation | ✅ |
| NFR-EXP-06 | Error handling | ✅ |
| NFR-EXP-07 | Rollback | ✅ |
| NFR-EXP-08 | No new deps | ✅ |
| NFR-EXP-09 | Engine boundary | ✅ |

### Tests

| Category | Count |
|----------|-------|
| PR1 (store) | 27 |
| PR2 (service+API+errors) | 42 |
| PR3 (comparison+export) | 14 |
| **Total** | **83** |
| All pass | ✅ |

### API Endpoints (7/7)

POST /experiment/create, GET /experiment/{id}, PATCH /experiment/{id}, GET /experiments, POST /experiment/{id}/run, POST /experiment/{id}/compare, GET /experiment/{id}/export

### CLI Commands (4/4)

lip exp create, lip exp list, lip exp compare, lip exp export

### Artifacts Archived

- `openspec/changes/fase-11-experiment-engine/exploration.md`
- `openspec/changes/fase-11-experiment-engine/proposal.md`
- `openspec/changes/fase-11-experiment-engine/design.md`
- `openspec/changes/fase-11-experiment-engine/tasks.md`
- `openspec/specs/experiment-engine/spec.md`

### What Changed

- Archive directory created: `openspec/changes/archive/2026-08-10-fase-11-experiment-engine/`
- Change artifacts moved to archive
- Delta specs synced to `openspec/specs/experiment-engine/spec.md`
- `PROJECT_STATUS.md` updated

### What Did NOT Change

- No code modified
- No tests modified
- No dependencies added
- No F12/F13/F14 features
- No commits altered

## Decision History

| Decision | Rationale |
|----------|-----------|
| D1: Polymorphic FK | Simpler schema; service validates; extensible for future engines |
| D2: Persisted comparison | Snapshots immutable → comparisons never stale; fast reads, audit trail |
| D3: Export in exporters/ | Respects existing seam; domain logic stays in experiments/ |
| D4: Identity scope (lottery_id, name) | Matches all existing engine patterns |

## Notes

- Comparison reads metrics from bt_results, MlMetric, DlMetric, OptResult at query time
- Comparison persists as immutable JSON snapshot — never recomputed
- ExperimentExporter uses stdlib json/csv — no new dependencies
- 7 error codes: EXPERIMENT_NOT_FOUND (404), EXPERIMENT_RETIRED (409), DUPLICATE_EXPERIMENT (409), SNAPSHOT_NOT_FOUND (404), SNAPSHOT_TYPE_MISMATCH (422), COMPARISON_INSUFFICIENT_RUNS (422), EXPORT_FORMAT_INVALID (422)
