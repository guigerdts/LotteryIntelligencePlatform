# Spec — Import Engine

**Change**: `fase-2-data-engine` · **Store**: `openspec` · **Date**: 2026-08-06
**Artifact**: spec (this change) — new capability `import-engine`, merged from change delta at archive time.

## Purpose

An auditable, reproducible, idempotent CSV import engine. Stream-parses official draw history, validates in two phases (structural whole-file, then semantic per-row), commits each draw atomically against the F1 natural key, records every run in `imports`/`import_errors`, imports on demand only (manual API + CLI + runner, NO scheduler), and generates immutable datasets on demand. F1 `core-domain` (CD-01..08) and `backend` REQ-01..09 are durable and unchanged.

## Requirements

### IE-01: CSV Column Contract

The import input MUST be a single CSV file (D1, no JSON). The header SHALL be exactly, in order: `draw_number`, `draw_date`, `numbers`, `super_number`, `jackpot`, `winners` (D2). `numbers` MUST contain only main numbers; `super_number` MUST be its own column, never appended to `numbers`. Delimiter MUST be comma; file MUST be UTF-8.

#### Scenario: canonical header accepted
- GIVEN a UTF-8 CSV with the six headers in verbatim order
- WHEN Phase A runs
- THEN Phase A passes and no unknown-column error is raised.

#### Scenario: super_number never in numbers
- GIVEN a row with 6 main numbers in `numbers` and a separate `super_number`
- WHEN the row is normalized
- THEN `super_number` is stored only in the super_number entity, never in `numbers`.

### IE-02: Phase A Structural Validation

The importer SHALL validate UTF-8, delimiter, required-column presence, unknown-column rejection, and header-contract compliance BEFORE any row processing (D6). On ANY Phase A failure the importer SHALL reject the ENTIRE file (nothing imported) and write an `imports` row with `status=rejected`.

#### Scenario: unknown column rejects whole file
- GIVEN a file with an extra "bonus" column
- WHEN Phase A runs
- THEN the whole file is rejected, no draws import, and the `imports` row has `status=rejected`.

#### Scenario: structural pass allows Phase B
- GIVEN a header-clean file yet with a malformed row
- WHEN Phase A passes
- THEN processing advances to Phase B (no whole-file rejection).

### IE-03: Phase B Per-Row Semantic Validation

Per row, the importer SHALL validate `draw_number`, `draw_date`, number count vs `numbers_to_select`, numbers within `min_number`..`max_number`, absence of intra-draw duplicates, `super_number` presence/range, and optional `jackpot`/`winners` (D6). Invalid rows MUST be recorded to `import_errors` (`import_id`, `row_number`, `draw_number`, `message`, `error_code`, `raw_row`); valid rows SHALL continue normal processing.

#### Scenario: out-of-range number records error, valid rows import
- GIVEN a file row with a number above `max_number`
- WHEN Phase B processes it
- THEN an `import_errors` row is written with `error_code` set, `error_rows` increments, and other valid rows still import.

#### Scenario: intra-draw duplicate rejected by app before DB
- GIVEN a row listing the same main number twice
- WHEN Phase B runs
- THEN the row is rejected to `import_errors` and is not committed.

### IE-04: Idempotent Re-Import

Imports SHALL rely on the F1 natural key `UNIQUE(lottery_id, draw_number)` (CD-02). Re-importing an existing draw SHALL be a no-op, counted in `duplicate_rows`. A second occurrence of a draw within the same file MUST be treated as a duplicate, skipped, and counted. Importing the EXACT same file again SHALL: be detected by `checksum`; STILL create a new `imports` row (the audit trail never loses an execution); record `imported_rows=0`, `duplicate_rows=total_rows`, and finish `completed`.

#### Scenario: re-import is a no-op
- GIVEN a lottery that already has draw 100
- WHEN a new import contains draw 100
- THEN the row is skipped, `duplicate_rows` increments, and no draw row is inserted twice.

#### Scenario: in-file duplicate counted
- GIVEN a file listing draw 100 twice
- WHEN both rows are processed
- THEN one imports and the second is counted in `duplicate_rows`.

#### Scenario: exact same file re-imported is audited
- GIVEN a file whose checksum matches a previous completed run
- WHEN it is imported again
- THEN a new `imports` row is created with `imported_rows=0`, `duplicate_rows=total_rows`, and `status=completed`, preserving the prior run intact.

### IE-05: Atomic Per-Draw Commit & Resume

Each draw SHALL be committed in its own transaction (reusing the F1 draw bundle). A crash SHALL roll back only the in-flight draw; the importer SHALL mark the run `failed`/`partial` and SHALL support resuming from unimported draws without re-inserting committed ones.

#### Scenario: crash rolls back only in-flight draw
- GIVEN a crash mid-import after N draws committed
- WHEN the run resumes
- THEN the in-flight draw is absent, committed draws are not duplicated, and `status` is marked partial/failed.

### IE-06: Audit Contract (`imports`)

Every run SHALL write one `imports` row with AT MINIMUM: `id`, `started_at`, `finished_at`, `status`, `source_file`, `checksum`, `total_rows`, `imported_rows`, `skipped_rows`, `duplicate_rows`, `error_rows`, `duration_ms` plus `import_type`, `lottery_id`, `started_by` (nullable), `engine_version`, `parser_version` (D3). `parser_version` SHALL be independent of `engine_version`: it identifies the exact CSV interpretation logic (column mapping, delimiters, normalization rules) used to parse the source file, so any run can be reproduced exactly. `status` MUST be one of `rejected|in_progress|completed|partial|failed`. Counters MUST reconcile: `total = imported + skipped + duplicate + error`.

**State machine**: a run starts `in_progress`; only valid transitions:
- `in_progress → completed` (all rows processed, no fatal error)
- `in_progress → partial` (some rows processed; a recoverable failure stopped the run — may be resumed)
- `in_progress → failed` (fatal/unreachable failure)
- `in_progress → rejected` (Phase A structural failure — whole file rejected, nothing imported; terminal)
- `partial → completed` (explicit resume that then completes)
- `partial → failed` (a resume hit a fatal error)

`completed`, `failed`, and `rejected` are TERMINAL states. Terminal states MUST NOT transition back to any active state (`in_progress`, `partial`). Once terminal, an `imports` row is immutable.

#### Scenario: completed run reconciles counters
- GIVEN a run that imported 3, skipped 0, duplicated 2, errored 1 from 6 rows
- WHEN the `imports` row is read
- THEN `total_rows=6` equals the sum `3+0+2+1` and `status=completed`.

#### Scenario: terminal state cannot reactivate
- GIVEN an `imports` row with `status=completed`
- WHEN a resume is attempted on that run
- THEN the transition is rejected and the row stays `completed` (the resume creates a new run instead).

#### Scenario: whole file rejection is terminal
- GIVEN a Phase A structural failure
- WHEN the run is created
- THEN `status` goes `in_progress → rejected` and never leaves `rejected`.

### IE-07: Import Types

The importer SHALL support manual API, CLI, and on-demand runner invocation, recording `import_type` as `manual | cli | runner`. `started_by` SHALL be nullable; `engine_version` and `parser_version` SHALL be recorded on every run.

#### Scenario: CLI import recorded as cli
- GIVEN an import launched from the CLI
- WHEN the run completes
- THEN `import_type="cli"`, `started_by` is set to the CLI user or null, `engine_version` and `parser_version` are recorded.

### IE-08: No Scheduler

The import engine SHALL NOT include any scheduler (D3). All imports are explicit, on-demand operations only. `scheduler_jobs` is explicitly not used.

#### Scenario: no scheduled import
- GIVEN no explicit manual/CLI/runner invocation
- WHEN the system idles
- THEN no import operation begins on its own.

### IE-09: On-Demand Dataset Generation (D5)

Dataset generation SHALL be an explicit, independent operation: filters → draw selection → checksum → `generator_version` → immutable dataset + lock (CD-03). Import SHALL only ingest draws (never auto-create datasets). Checksum SHALL depend only on dataset content and algorithm; `generator_version` SHALL be recorded (CD-03).

#### Scenario: import does not auto-create a dataset
- GIVEN a completed bulk import
- WHEN no generation is invoked
- THEN no `datasets` row is created by the import.

#### Scenario: dataset generated on demand
- GIVEN a set of drawn draws and explicit invocation
- WHEN dataset generation runs
- THEN a new immutable, locked dataset version with computed checksum is created.

### IE-10: Portability (CD-08)

The `imports`/`import_errors` migration SHALL be additive and portable (no PostgreSQL- or SQLite-specific DDL, `batch_mode` per REQ-09). Import loading paths SHALL be N+1-free (batch/joined loads, repositories own loading per CD-07).

#### Scenario: additive portable migration
- GIVEN the existing F1 schema
- WHEN `alembic upgrade head` adds the two tables
- THEN draws/datasets are untouched and the migration uses only portable ops.

### IE-11: API Surface

`POST /draws/import` (execute an import from a described source) and `POST /draws/upload` (multipart CSV upload that runs the import) SHALL be mounted (F1 left them unmounted). Both SHALL return the Fase 0 envelope with an `imports` summary. Invalid CSV maps to `validation_error` (422); a missing lottery maps to `RESOURCE_NOT_FOUND` (404); per-row duplicates are NOT errors (IE-04) and SHALL NOT raise a duplicate error on import.

#### Scenario: upload rejects malformed CSV
- GIVEN a CSV that fails Phase A structural validation
- WHEN `POST /draws/upload` is called
- THEN the response is 422 `{code:"validation_error"}` and nothing is imported.
## Non-Goals

No scheduler (D3); no JSON input (D1); no remote/external source; no dependency on a real historical file (D4); no dataset auto-creation during import (D5); no F3 statistics; no dataset CRUD endpoints (M4).
