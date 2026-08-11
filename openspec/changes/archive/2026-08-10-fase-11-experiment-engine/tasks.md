# Tasks: F11 — Experiment Engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650–750 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1) → PR 2 (S2) → PR 3 (S3) |
| Delivery strategy | ask-on-risk |
| Chain strategy | **stacked-to-main** (user chose 2026-08-10) |

Decision needed before apply: **RESOLVED** — 3 PRs stacked-to-main

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| S1 | Foundation: migration + models + types + store | PR 1 | `backend/.venv/bin/pytest tests/test_exp_store.py -v` | N/A — unit tests only, no server | Remove `experiments/{types,version,fingerprint,snapshot_store}.py`, `models/exp_*.py`, migration 0013 |
| S2 | Engine + service + API + CLI + errors | PR 2 | `backend/.venv/bin/pytest tests/test_exp_service.py tests/test_exp_api.py -v` | `lip exp create --lottery-id 1 --name "test"` | Remove `experiments/engine.py`, `services/exp_service.py`, `api/v1/exp.py`; revert `cli.py`, `router.py`, `errors.py` |
| S3 | Comparison + export | PR 3 | `backend/.venv/bin/pytest tests/test_exp_comparison.py tests/test_exp_export.py -v` | `GET /experiment/1/export?format=json` | Remove `exporters/experiment_exporter.py`, comparison logic in `exp_service.py` |

## Phase 1: Foundation — Migration + Models + Types + Store

- [x] T-EXP-001 | Create `alembic/versions/0013_exp_tables.py`: tables `exp_experiments`, `exp_runs`, `exp_comparisons` with CHECK constraints, unique `(lottery_id, name, fingerprint)`, indexes. Downgrade drops 3 tables. | `alembic/versions/0013_exp_tables.py` | None | EXP-001, EXP-002, EXP-003, NFR-EXP-07 | Test: `alembic upgrade 0013` creates tables; `alembic downgrade -1` removes them | ~50 impl |
- [x] T-EXP-002 | Create ORM models: `ExpExperiment` (9 cols), `ExpRun` (8 cols), `ExpComparison` (4 cols) mirroring BtSnapshot pattern. | `models/exp_experiment.py`, `models/exp_run.py`, `models/exp_comparison.py` | T-EXP-001 | EXP-001, EXP-002, EXP-003 | Test: models instantiate, `__table_args__` has correct constraints | ~40 impl |
- [x] T-EXP-003 | Modify `models/__init__.py` to re-export `ExpExperiment`, `ExpRun`, `ExpComparison` for alembic `target_metadata`. | `models/__init__.py` | T-EXP-002 | EXP-001 | Test: `from backend.app.models import ExpExperiment` succeeds | ~3 impl |
- [x] T-EXP-004 | Create `experiments/types.py`: `ExperimentConfig` and `ComparisonResult` dataclasses. | `experiments/types.py` | None | EXP-005, EXP-006 | Test: dataclass instantiation, field access | ~15 impl |
- [x] T-EXP-005 | Create `experiments/version.py`: `EXPERIMENT_GENERATOR_VERSION = "1.0.0"`. | `experiments/version.py` | None | EXP-002 | Test: constant equals `"1.0.0"` | ~3 impl |
- [x] T-EXP-006 | Create `experiments/fingerprint.py`: `compute_exp_fingerprint(name, lottery_id, config_json, description, status)` using `hashlib.sha256`. | `experiments/fingerprint.py` | None | EXP-002, NFR-EXP-02 | Test: same inputs → same fingerprint; different config → different fingerprint | ~15 impl |
- [x] T-EXP-007 | Create `experiments/snapshot_store.py`: `ExpSnapshotStore` with `next_version()`, `find_by_fingerprint()`, `create()`, `mark_failed()`, `get()`, `update()`, `list_by_lottery()`. | `experiments/snapshot_store.py` | T-EXP-002, T-EXP-006 | EXP-001, EXP-002, EXP-003, EXP-004 | Test: next_version monotonic, create/get/update CRUD, mark_failed, idempotent fingerprint, lottery isolation | ~70 impl |
- [x] T-EXP-008 | Write RED+GREEN tests for store persistence: CRUD lifecycle, version monotonicity, fingerprint idempotency, lottery isolation, mark_failed. | `tests/test_exp_store.py` | T-EXP-007 | EXP-001, EXP-002, EXP-004, NFR-EXP-03, NFR-EXP-05 | All store tests pass via `pytest tests/test_exp_store.py` | ~80 test |

## Phase 2: Engine + Service + API + CLI + Errors

- [ ] T-EXP-009 | Modify `services/errors.py`: add `ExperimentError(ServiceError)` and `ComparisonError(ServiceError)` with 7 error codes as class constants. | `services/errors.py` | None | EXP-008, NFR-EXP-06 | Test: `ExperimentError.__mro__` includes `ServiceError` | ~20 impl |
- [ ] T-EXP-010 | Modify `api/errors.py`: add 7 entries to `_CODE_TO_STATUS` mapping (`EXPERIMENT_NOT_FOUND`→404, `EXPERIMENT_RETIRED`→409, `DUPLICATE_EXPERIMENT`→409, `SNAPSHOT_NOT_FOUND`→404, `SNAPSHOT_TYPE_MISMATCH`→422, `COMPARISON_INSUFFICIENT_RUNS`→422, `EXPORT_FORMAT_INVALID`→422). | `api/errors.py` | T-EXP-009 | EXP-008, NFR-EXP-06 | Test: each code maps to correct HTTP status | ~10 impl |
- [ ] T-EXP-011 | Create `services/exp_service.py`: `ExpService` with `create()`, `get()`, `update()`, `retire()`, `add_run()`, `list_experiments()`, `compare()`, `export()`. Session injection, private helpers. Validates engine_snapshot_id against `ENGINE_TABLES`. | `services/exp_service.py` | T-EXP-007, T-EXP-009 | EXP-001, EXP-002, EXP-003, EXP-004, EXP-005, EXP-006, NFR-EXP-03, NFR-EXP-05, NFR-EXP-09 | Test: create/get/update/retire lifecycle, add_run validates snapshot, list filters, retired rejects mutation, idempotent fingerprint | ~90 impl |
- [ ] T-EXP-012 | Create `experiments/engine.py`: `ExperimentEngine` thin orchestrator delegating to `ExpSnapshotStore` + `ExpService`. | `experiments/engine.py` | T-EXP-011 | EXP-001 | Test: engine delegates correctly to store and service | ~20 impl |
- [ ] T-EXP-013 | Create `api/v1/exp.py`: API router with 7 endpoints (`POST /experiment/create`, `GET /experiment/{id}`, `PATCH /experiment/{id}`, `GET /experiments`, `POST /experiment/{id}/run`, `POST /experiment/{id}/compare`, `GET /experiment/{id}/export`). Pydantic v2 schemas, `SuccessEnvelope`. | `api/v1/exp.py` | T-EXP-011 | EXP-001, EXP-003, EXP-004, EXP-005, EXP-006 | Test: each endpoint returns correct status and payload | ~70 impl |
- [ ] T-EXP-014 | Modify `api/v1/router.py`: include `exp_router` with prefix. | `api/v1/router.py` | T-EXP-013 | EXP-001 | Test: `GET /experiments` route resolves | ~3 impl |
- [ ] T-EXP-015 | Modify `cli.py`: add `lip exp` subparser with 4 subcommands (`create`, `list`, `compare`, `export`). stdlib argparse. | `cli.py` | T-EXP-011 | EXP-007 | Test: `lip exp create --lottery-id 1 --name "test"` outputs JSON | ~40 impl |
- [ ] T-EXP-016 | Write RED+GREEN tests for service unit: create/get/update/retire lifecycle, add_run validation, list filters, idempotency. | `tests/test_exp_service.py` | T-EXP-011 | EXP-001–EXP-004, NFR-EXP-03, NFR-EXP-05 | All service unit tests pass | ~90 test |
- [ ] T-EXP-017 | Write RED+GREEN integration tests for API: 7 endpoints, error codes (404, 409, 422), envelope format. | `tests/test_exp_api.py` | T-EXP-013 | EXP-001–EXP-007, EXP-008 | All API tests pass via `pytest tests/test_exp_api.py` | ~80 test |

## Phase 3: Comparison + Export

- [x] T-EXP-018 | Extend `services/exp_service.py`: add `compare()` reads metrics from referenced engine tables (`bt_results`, `MlMetric`, `DlMetric`, `OptResult`), builds sorted matrix, persists in `exp_comparisons`. Idempotent for same run_ids. | `services/exp_service.py` | T-EXP-011 | EXP-005, NFR-EXP-03, NFR-EXP-04 | Test: 2-run comparison returns correct matrix; <2 runs raises `COMPARISON_INSUFFICIENT_RUNS`; same run_ids returns cached | ~50 impl |
- [x] T-EXP-019 | Extend `api/v1/exp.py`: wire `POST /experiment/{id}/compare` and `GET /experiment/{id}/export` endpoints. | `api/v1/exp.py` | T-EXP-013, T-EXP-018 | EXP-005, EXP-006 | Test: compare returns matrix; export returns JSON/CSV | ~20 impl |
- [x] T-EXP-020 | Extend `cli.py`: wire `lip exp compare` and `lip exp export` subcommands. | `cli.py` | T-EXP-015, T-EXP-018 | EXP-007 | Test: `lip exp compare --experiment-id 1 --run-ids 1,2` outputs JSON | ~15 impl |
- [x] T-EXP-021 | Create `exporters/experiment_exporter.py`: `ExperimentExporter.export_json(data)` and `export_csv(data)` using stdlib `json` + `csv`. JSON: `{experiment, runs, comparisons}`. CSV: `run_id, run_label, engine_type, engine_snapshot_id, engine_fingerprint, notes, created_at`. | `exporters/experiment_exporter.py` | None | EXP-006, NFR-EXP-08 | Test: JSON valid, CSV has header row, round-trip matches | ~50 impl |
- [x] T-EXP-022 | Write RED+GREEN tests for comparison: 2-run matrix correctness, insufficient runs error, idempotent cached comparison, deterministic sorted output. | `tests/test_exp_comparison.py` | T-EXP-018 | EXP-005, NFR-EXP-02, NFR-EXP-03, NFR-EXP-04 | All comparison tests pass | ~50 test |
- [x] T-EXP-023 | Write RED+GREEN tests for export: JSON structure, CSV columns, invalid format error, idempotent export output. | `tests/test_exp_export.py` | T-EXP-021, T-EXP-018 | EXP-006, NFR-EXP-02, NFR-EXP-03 | All export tests pass | ~40 test |

## Traceability Matrix

| Requirement | Slice | Tasks | Test Scenarios |
|-------------|-------|-------|----------------|
| EXP-001 CRUD | S1+S2 | T-EXP-001,002,003,007,011,012,013 | create, update, retire, duplicate (idempotent) |
| EXP-002 Version | S1 | T-EXP-005,006,007 | version increments, fingerprint duplicate, different config |
| EXP-003 Run Assoc | S1+S2 | T-EXP-001,002,007,011,013 | valid run, invalid snapshot type, missing snapshot |
| EXP-004 History | S2 | T-EXP-011,013 | list by lottery, filter by status+date, empty result |
| EXP-005 Comparison | S3 | T-EXP-004,011,018,019,022 | 2-run compare, insufficient runs, idempotent |
| EXP-006 Export | S3 | T-EXP-004,019,021,023 | JSON export, CSV export, invalid format |
| EXP-007 CLI | S2+S3 | T-EXP-015,020 | create via CLI, list via CLI |
| EXP-008 Errors | S2 | T-EXP-009,010 | all 7 error codes map to correct HTTP status |
| NFR-EXP-01 Perf | S2 | T-EXP-016,017 | service and API tests verify response |
| NFR-EXP-02 Determinism | S1+S3 | T-EXP-006,022,023 | fingerprint same→same, comparison sorted, export consistent |
| NFR-EXP-03 Idempotency | S1+S2+S3 | T-EXP-007,011,018,023 | fingerprint dedup, comparison cache, export stable |
| NFR-EXP-04 Immutability | S3 | T-EXP-018,022 | comparison never mutated, retired rejects mutation |
| NFR-EXP-05 Isolation | S1+S2 | T-EXP-007,011,016 | lottery-scoped queries, cross-lottery invisible |
| NFR-EXP-06 Error Taxonomy | S2 | T-EXP-009,010 | ServiceError subclass, HTTP mapping |
| NFR-EXP-07 Rollback | S1 | T-EXP-001 | `alembic downgrade -1` drops exp_* tables only |
| NFR-EXP-08 No New Deps | All | T-EXP-006,021 | stdlib json+csv only, no imports of external packages |
| NFR-EXP-09 Engine Boundary | S2 | T-EXP-011 | no module-level bt_*/ml_*/dl_*/opt_* imports |
