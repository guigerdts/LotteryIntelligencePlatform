# Tasks: Fase 2 Data Engine (Importation)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1400–1800 across 3 slices (+tests) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Slice 1 → 2 → 3 |
| Delivery strategy | ask-on-risk → resolves: chained (forecast high) |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Note: no git remote configured — PRs deferred until remote exists; each slice ships as work-unit commits mapping 1:1 to one stacked-to-main PR (F1 precedent).

### Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| 1 | import core (parse/normalize/validate) | PR-1 | `uv run pytest tests/test_import_core.py -q` | py parse over CSV fixture matrix via FileAdapter | revert `importers/` + fixtures; no schema touched |
| 2 | persistence + state machine + resume | PR-2 | `uv run pytest tests/test_import_service.py tests/test_migrations.py -q` | tmp SQLite run_import → resume → re-import | `alembic downgrade 0003`; revert models+repos+service |
| 3 | surface + dataset on demand | PR-3 | `uv run pytest tests/test_import_api.py tests/test_dataset_generate.py -q` | TestClient 200/404/409/422; `lip dataset-generate` | revert `api/v1/draws.py`, `cli.py`; service stays green |

## Gates (every PR must pass ALL G1–G7; import adds G8)

- G1 `uv run ruff check .` + `ruff format --check .` clean (line-length 100)
- G2 `uv run pytest -q` green (Fase 0/F1 suite incl. CD-01..08 preserved)
- G3 `alembic upgrade head` (0003+0004) on empty base succeeds
- G4 `alembic downgrade` → re-upgrade succeeds (idempotent forward/back, drops import_errors→imports)
- G5 no regression vs F1; CD-01..08 + REQ-01..09 untouched
- G6 portable DDL only (batch_mode, no PG/SQLite triggers/partial indexes)
- G7 self-contained PR: compilable, testable, no deferred debt
- G8 CSV fixtures (canonical/unknown column/bad delimiter/non-UTF-8/1 row per error_code/in-file dup); state transitions; concurrency IMPORT_CONFLICT; resume contract; checksum re-import; dataset on-demand checksum+immutable+lock; counters reconcile (`3+0+2+1=6`); duplicates NEVER DUPLICATE_RESOURCE

## Dependency Matrix

| Slice | Delivers | Blocks | Enables |
|-------|----------|--------|---------|
| 1 | `importers/version.py`(PARSER_VERSION); `sources.py` CSV FileAdapter(stream)+sha256; `normalize.py`(NormalizedDraw); `validate.py` Phase A+Phase B(D6); CSV fixtures; unit tests | S2 importer | S2 operators consume pure parse pipeline |
| 2 | models `import_job`/`import_error`; repositories; `importer.py` operators; `ImportService.run_import` (state machine, per-draw tx, counters, resume D-D2, checksum D-H); migrations 0003+0004; integration tests | S3 mount | S3 thin wiring over use cases |
| 3 | `POST /draws/import`+`/draws/upload` (forced manual); register IMPORT_CONFLICT/IMPORT_STATE_CONFLICT (409); CLI + pyproject console script; `generate_dataset`; API tests | — terminal | Fase 2 contract complete; F3 readiness |

## Slice 1 — Import Core Pipeline (PR-1)

- [x] S1-01 `importers/version.py` — `PARSER_VERSION` const (independent of `settings.app_version`)
- [x] S1-02 `importers/sources.py` — CSV `FileAdapter`: stream rows, streamed sha-256 checksum, delimiter/UTF-8 detect
- [x] S1-03 `importers/normalize.py` — `NormalizedDraw`; date/number parse, super_number never in numbers (IE-01)
- [x] S1-04 `importers/validate.py` — `validate_phase_a` (UTF-8/delimiter/headers/unknown-col reject) + `validate_row` (per-error_code taxonomy §7); pure, no DB
- [x] S1-05 `tests/test_import_core.py` + `tests/fixtures/*.csv` — Phase A reject matrix, per-code Phase B, checksum stability, PARSER_VERSION
- [x] S1-06 Run gates G1, G2, G5, G6

## Slice 2: Persistence + Audit + State Machine

- [x] S2-01 `models/import_job.py` + `models/import_error.py` (PK/FK RESTRICT, CHECK status/import_type/counters, tz-aware UTC)
- [x] S2-02 `repositories/import_repository.py` (create, positional status, conditional terminal UPDATE rowcount-guard, in-progress same-lottery check) + `import_error_repository.py` (batch add_many)
- [x] S2-03 `alembic/versions/0003_imports_audit.py` — tables+CHECK+FK only; import perf indexes deferred to 0004
- [x] S2-04 `alembic/versions/0004_import_performance_indexes.py` — import perf indexes (functionally optional, mirror 0002)
- [x] S2-05 `importers/importer.py` — stream loop + per-draw tx (natural-key dup→duplicate_rows NOT DUPLICATE_RESOURCE; create→numbers→super→counters+last_processed_row)
- [x] S2-06 `services/import_service.py` `run_import` — lifecycle: Phase A→rejected; in_progress→completed/partial/failed; resume contract (checksum+parser_version+engine_version+lottery match else new run); concurrency IMPORT_CONFLICT (same lottery in_progress)
- [x] S2-07 `tests/test_import_service.py` + `test_migrations.py` — counters `3+0+2+1=6`; resume partial→completed no dup; checksum re-import (new row, duplicate=total); concurrent→IMPORT_CONFLICT; upgrade/downgrade; terminal immutability
- [x] S2-08 Run gates G1–G6, G8

## Slice 3: Surface + Dataset on Demand

- [x] S3-01 `api/v1/draws.py` mount `POST /draws/import` (JSON `{lottery_code,source_file,resume}`) + `POST /draws/upload` (multipart), both force `import_type="manual"`; envelope summary (200/404/409/422)
- [x] S3-02 `api/errors.py` register `IMPORT_CONFLICT: 409`, `IMPORT_STATE_CONFLICT: 409`
- [x] S3-03 `cli.py` + `pyproject.toml` console script — `lip import --lottery --file [--resume]` (import_type="cli", started_by=getpass), `lip dataset-generate` (IE-08 no scheduler)
- [x] S3-04 `ImportService.generate_dataset` (D5/IE-09) — filters→batched draw select→sha256 checksum→`dataset_service.create_dataset(checksum, is_locked=True)`; import never creates datasets
- [x] S3-05 `dataset_service.create_dataset` accepts additive `checksum` (default None) — CD-03 preserved
- [x] S3-06 `tests/test_import_api.py` (upload 200/422/404; import 404/409/422/200) + `test_dataset_generate.py` (checksum stable, immutable+lock, no auto-dataset)
- [x] S3-07 Run ALL gates G1–G8; no-debt review