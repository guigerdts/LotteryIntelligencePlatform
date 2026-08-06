# Proposal: Fase 2 — Data Engine (Importation)

**Change**: `fase-2-data-engine` · **Store**: openspec · **Date**: 2026-08-06

## Intent

Build the **Data Engine** importation engine. F1 already ships ~60% of the contract: natural-key idempotency (`UNIQUE(lottery_id,draw_number)` + `get_by_natural_key`/`upsert_draw`), atomic per-draw bundle (`draw_service.create_draw_bundle`), service-owned rule validation (CD-06 → 422), immutable+locked datasets, typed-error taxonomy→envelope, N+1-free loaders, un-mounted `/draws/import` + `/draws/upload`, and empty `importers/` seam. F2 bridges the gap: stream-parse CSV → validate/normalize per lottery rules → commit full history in auditable batches → on-demand immutable dataset generation. NO scheduler in this change (D3).

## Decisions (D1–D5) — adopted binding

- **D1** — Input format: **CSV only**. No JSON in this change.
- **D2** — Official CSV columns (per draw): `draw_number`, `draw_date`, `numbers`, `super_number`, `jackpot`, `winners`. `numbers` holds only main numbers; `super_number` ALWAYS in its own column, never appended.
- **D3** — No scheduler. Manual API + CLI + on-demand runner only. New `imports` audit contract, AT MINIMUM: `id`, `started_at`, `finished_at`, `status`, `source_file`, `checksum`, `total_rows`, `imported_rows`, `skipped_rows`, `duplicate_rows`, `error_rows`, `duration_ms`, plus audit fields `import_type` (`manual | cli | runner`), `lottery_id`, `started_by` (nullable), `engine_version`.
- **D4** — Official CSV format defined in spec + validated via fixtures/tests; no dependency on a real historical file.
- **D5** — Datasets generated ON DEMAND only: Filters → Draw selection → Checksum → Generator version → Immutable → Lock. No auto dataset creation during import; import only ingests draws.
- **D6** — CSV parser validation in TWO phases. **Phase A (structural)**, BEFORE any processing: `UTF-8`, `delimiter`, required columns, unknown-column rejection, header-contract compliance. If Phase A fails → reject the ENTIRE file (nothing imported). **Phase B (semantic)**, per row: `draw_number`, `draw_date`, number count, allowed range, intra-draw duplicates, `super_number`, `jackpot`, `winners`. Invalid rows are recorded to `import_errors`; valid rows continue normal processing.

## Capabilities

### New Capabilities
- `import-engine`: CSV parsing/normalization, validation, per-draw atomic import, audit (`imports`/`import_errors`), manual + CLI import, on-demand dataset generation for import history.

### Modified Capabilities
- None — `core-domain` (CD-01..08) is durable and MUST NOT change; `backend` REQ-01..09 unchanged. Only new endpoints land on existing routers.

## Approach

Stream-parse → **Phase A structural validation** (reject whole file on failure) → normalize → **Phase B per-row semantic validation** (invalid rows → `import_errors`, valid rows continue) → **commit-per-draw bundle** (one tx per draw; reuses F1 bundle + natural key; no staging table; does NOT load full file into RAM; crash rolls back only in-flight draw → natural resume). Source-adapter seam with a CSV `FileAdapter` concrete now (remote/external sources deferred). Additive portable alembic migration for `imports` + `import_errors`.

| Layer | Responsibility |
|---|---|
| `importers/sources` | CSV `FileAdapter` (stream) → normalized row |
| `importers/normalize` | cleaning, date/number parse, sheet-level pre-pass |
| `importers/validate` | draw count vs `numbers_to_select` (CD-06); row errors vs reject class |
| `importer`/`services/import_service` | orchestrate batches, write `imports` row + counters |
| repos/API | `imports`/`import_errors` persist, `POST /draws/import`, `POST /draws/upload` |

## Scope

**In**: CSV parser + fixtures (D4); two-phase validation (D6): Phase A structural full-file rejection + Phase B per-row semantic errors; clean/normalize; per-draw atomic commit + resume; duplicate detection; error registration; `imports`+`import_errors` tables (audit contract incl. `import_type`/`lottery_id`/`started_by`/`engine_version`); manual API + CLI + on-demand runner; on-demand dataset generation w/ checksum + lock.

**Out of Scope / Non-goals**: scheduler (D3); JSON (D1); remote/external source; real-file dependency (D4); dataset auto-creation during import (D5); F3 statistics; dataset CRUD endpoints (M4).

## Contract & Constraints

Immutable/locked datasets (CD-03/DATASET_LOCKED); soft-delete (CD-05); UNIQUE constraints (CD-02); idempotent re-import via natural key; atomic-per-draw; N+1-free loaders (CD-07); PG-portable migrations (CD-08/REQ-09); envelope error codes (F0). New `imports` DTO maps 1:1 (table `imports`): `id`, `started_at`, `finished_at`, `status`, `source_file`, `checksum`, `total_rows`, `imported_rows`, `skipped_rows`, `duplicate_rows`, `error_rows`, `duration_ms` + audit `import_type` (`manual | cli | runner`), `lottery_id`, `started_by` (nullable), `engine_version` (+ `created_at`). `import_errors`: `import_id`, `row_number`, `draw_number`, `message`, `error_code`, `raw_row`.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/backend/app/importers/` | New/Modify | Fill seam: source adapter, normalize, validate |
| `backend/src/backend/app/models/{import_job,import_error}.py` | New | ORM for the two new tables |
| `backend/src/backend/app/repositories/{import_repo,import_error_repo}.py` | New | audit writes, error listing |
| `backend/src/backend/app/services/import_service.py` | New | importer use case; dataset on-demand |
| `backend/src/backend/app/api/v1/{draws,router}.py` | Modify | mount `/draws/import`, `/draws/upload` |
| `backend/alembic/versions/000X_imports.py` | New | additive: `imports`/`import_errors` |
| `backend/tests/*` + fixtures | New | CSV fixtures, import contract tests |

## Rollback Plan

Per-draw tx (no partial multi-draw commit) → `alembic downgrade <prev>` drops ONLY `imports`/`import_errors` → `git revert`; docs revert. CD-01..08 untouched, so rollback is clean with no data loss to draws/datasets.

## Success Criteria (DoD)

- [ ] Full-history CSV imports all valid draws; draw/number constraints hold.
- [ ] Phase A structural violation (UTF-8/delimiter/columns/header) → whole file rejected, nothing imported.
- [ ] Phase B per-row semantic failures classified and persisted to `import_errors`; valid rows still imported; `error_rows` accurate.
- [ ] Duplicates detected via `UNIQUE(lottery_id,draw_number)`; counted in `duplicate_rows`.
- [ ] Row errors classified and persisted to `import_errors`; `error_rows` accurate.
- [ ] Every run writes a complete auditable `imports` row (D-03 fields).
- [ ] Dataset generated on demand: filters→selection→checksum→generator_version→immutable→locked.
- [ ] CD-01..08 contract-preservation tests still green; PG-portable migration.

## Delivery Forecast

3 chained PR slices, each under the 400-line review budget (~1.4–1.8k lines total w/ tests):
1. CSV adapter + normalization/validation + fixtures + tests.
2. Importer runner + `imports`/`import_errors` migration + per-draw commit + CLI + duplicate/error registration.
3. Manual API (`/draws/import`, `/draws/upload`) + on-demand dataset generation + wiring/tests.

## Approval Gate

Interactive mode — **approval-gated**. Do NOT auto-advance to sdd-spec without explicit user approval of D1–D5 and scope.