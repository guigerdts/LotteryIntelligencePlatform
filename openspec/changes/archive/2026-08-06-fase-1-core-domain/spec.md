# Spec — Fase 1 Core Domain

**Change**: `fase-1-core-domain` · **Store**: `openspec` · **Date**: 2026-08-06
Part 1 = delta on `openspec/specs/backend/spec.md`; Part 2 = new capability `core-domain`. Traceable to [D1]–[D16] and rules 1–6.

---

# Part 1 — Delta for backend

## MODIFIED Requirements

### REQ-05: SQLite Bootstrap & Schema Ownership

The app SHALL create the SQLite DB file at the configured `paths`/`database` location (on `init_db` or startup) when absent. The schema SHALL be owned exclusively by Fase 1 alembic migrations (REQ-09), never by `init_db` or ORM auto-create. All DB access SHALL go through the SQLAlchemy ORM boundary in `repositories/` so PostgreSQL is a config-only dialect swap; SQLite-only code paths MUST NOT be hard-coded.
(Previously: "No schema/migrations (Fase 1)" — the file was created empty with zero tables.)

**Acceptance**
- [ ] `init_db`/startup creates the file when absent; no table exists until `alembic upgrade head`.
- [ ] Engine construction is dialect-driven (config-only SQLite→PostgreSQL swap), with no SQLite-specific code outside the ORM boundary.

#### Scenario: db file created, schema via migrations
- GIVEN a clean configured DB path
- WHEN the init_db/boot step runs
- THEN the file exists with no tables; tables appear only after `alembic upgrade head` (REQ-09).

## ADDED Requirements

### REQ-09: Alembic Migration Ownership

Alembic (`backend/alembic/`, `env.py` → `target_metadata = Base.metadata`) SHALL be the sole schema owner [D10]. Migrations SHALL use only portable operations (`batch_mode` for SQLite DDL); PG-specific or SQLite-specific DDL MUST NOT be introduced. `init_db` SHALL NOT create schema.

#### Scenario: migrations create the F1 schema
- GIVEN a fresh DB file created by `init_db`
- WHEN `alembic upgrade head` runs
- THEN tables `lottery`, `draw`, `draw_numbers`, `super_number`, `datasets`, `dataset_draws` exist with their constraints.

---

# Part 2 — core-domain Specification (new capability)

## Purpose

Persisted core domain: Lottery, Draw, DrawNumber, SuperNumber, Dataset + `dataset_draws` join, with portable constraints, tz-aware UTC timestamps, soft-delete semantics, and reproducibility (immutable versioned datasets, raw-only storage, persisted generation metadata).

## Requirements

### CD-01: Entities & Relationships

F1 SHALL expose tables `lottery`, `draw`, `draw_numbers`, `super_number`, `datasets`, `dataset_draws` (names verbatim from DATABASE_SCHEMA.md [M1]). Lottery rules SHALL persist as `lottery` columns: `code` String(32) UNIQUE NOT NULL, `name`, `country` ISO 3166-1 alpha-2 String(2), `description`, `min_number`, `max_number`, `numbers_to_select`, nullable `super_number_min`/`super_number_max` [D1, D14]. `draw.draw_number` SHALL keep its doc-conformant name despite the `DrawNumber` entity [D15].

#### Scenario: lottery with rule columns
- GIVEN a valid rule set
- WHEN a lottery row is created
- THEN all rule columns persist and `country` stores an alpha-2 code.

#### Scenario: duplicate lottery code rejected
- GIVEN an existing lottery with code "LOTO"
- WHEN a second lottery with the same code is inserted
- THEN the DB rejects the insert (UNIQUE violation).

### CD-02: Draw & Number Constraints

`draw` SHALL enforce `UNIQUE(lottery_id, draw_number)` and index `(lottery_id, draw_date)`; `draw_date` SHALL be a `Date` with separate tz-aware UTC `created_at` [D3, D12, D4]. `draw_numbers` SHALL enforce `UNIQUE(draw_id, position)` and `UNIQUE(draw_id, number)` [C7]. `super_number` SHALL be 0..1 per draw via `UNIQUE(draw_id)`, `value` NOT NULL [D2].

#### Scenario: duplicate draw rejected
- GIVEN a lottery with draw_number 100
- WHEN inserting draw_number 100 for the same lottery
- THEN the DB rejects it (UNIQUE(lottery_id, draw_number)); the same number for another lottery succeeds.

#### Scenario: repeated number inside a draw rejected
- GIVEN a draw with position 1 = 7
- WHEN inserting position 2 = 7
- THEN the DB rejects it (UNIQUE(draw_id, number)).

#### Scenario: second super number rejected
- GIVEN a draw with one super_number
- WHEN inserting a second super_number for the same draw
- THEN the DB rejects it (UNIQUE(draw_id)).

### CD-03: Dataset Immutability & Reproducibility

`datasets` SHALL enforce global `UNIQUE(version)` [D16] and persist `description`, `lottery_id`, `filters`, `generator_version`, `checksum` (nullable, computed in F2), `created_at`, `is_locked` [D5]. A created dataset SHALL be immutable: existing datasets MUST NOT be updated or re-composed; any filter/composition change SHALL create a NEW dataset version [rule 2]. `checksum` SHALL depend only on dataset content and the checksum algorithm; `generator_version` SHALL be documented as part of the reproducibility contract [rule 3]. Composition SHALL use `dataset_draws` with `UNIQUE(dataset_id, draw_id)` [D5, D6].

#### Scenario: locked dataset is immutable
- GIVEN an `is_locked` dataset
- WHEN an update to its filters or draw composition is attempted
- THEN the operation is rejected; the dataset is never mutated.

#### Scenario: composition change creates a new version
- GIVEN an immutable dataset v1
- WHEN a different draw set is needed
- THEN a new dataset (v2) is created; v1 remains byte-identical.

#### Scenario: checksum is stable
- GIVEN the same draw set, filters, and checksum algorithm
- WHEN `checksum` is recomputed
- THEN the value is identical — content and algorithm only.

### CD-04: Raw-Only & Column Conventions

F1 SHALL persist only raw official results (`draw`, `draw_numbers`, `super_number`); derived values SHALL NOT be stored before F4 `feature_value` [D13]. `jackpot` SHALL be `Numeric(18,2)` nullable; `winners` Integer nullable [D7]. All timestamps SHALL be tz-aware UTC [D4]. No DB-native enums SHALL be used [D11].

#### Scenario: null jackpot draw persists
- GIVEN an official draw without a published jackpot
- WHEN the draw is stored
- THEN `jackpot` is NULL and the row is valid.

### CD-05: Soft-Delete & Delete Semantics

All functional queries MUST exclude rows with `is_deleted=true` by default [rule 5, D8]. Draws SHALL be soft-deleted (no hard DELETE); restoring a draw SHALL restore its numbers and super_number with FK integrity [rule 5]. Deleting a lottery SHALL be RESTRICTed while draws exist [D9]. Deleting a draw referenced by `dataset_draws` SHALL be blocked (FK RESTRICT) [D8].

#### Scenario: soft-deleted draw filtered out
- GIVEN a soft-deleted draw
- WHEN draws are listed
- THEN the draw is absent, while its row persists with `is_deleted=true`.

#### Scenario: restore preserves children
- GIVEN a soft-deleted draw with numbers and a super_number
- WHEN the draw is restored
- THEN it reappears with all its numbers and super_number intact.

#### Scenario: lottery delete restricted
- GIVEN a lottery with at least one draw
- WHEN `DELETE /lotteries/{id}` is called
- THEN the API returns 409 (FK RESTRICT) and the lottery remains.

### CD-06: Database vs Application Validation

The DATABASE SHALL own structural validation: UNIQUE, CHECK, FK constraints (CD-01..05). APPLICATION logic SHALL own cross-entity invariants and behavior: draw_number count vs `numbers_to_select` (validated in F2 import, per C8), immutability enforcement for locked datasets, soft-delete filtering, code-based lookup [rule 6].

#### Scenario: DB constraints are independent of app logic
- GIVEN an app that skips its own validation
- WHEN a duplicate `(lottery_id, draw_number)` is inserted
- THEN the DB still rejects it.

### CD-07: Repositories & CRUD

F1 SHALL ship per-entity repositories over the DI `Session` for all six tables [API_SPEC §3/§4]. CRUD under `api/v1`: `GET/POST/PUT/DELETE /lotteries[/{id}]`, `GET /draws[/{id}]` with pagination/filtering/ordering and `?lottery=<code>` lookup; all responses SHALL use the Fase 0 envelope [REQ-02]. `/draws/latest`, `/draws/import`, `/draws/upload` are Fase 2; Dataset CRUD endpoints are deferred (M4 — no `/datasets` contract invented here).

#### Scenario: draw list filtered by lottery code
- GIVEN draws of two lotteries
- WHEN `GET /draws?lottery=LOTO` is called
- THEN only LOTO's draws are returned in the envelope.

#### Scenario: missing draw returns envelope 404
- GIVEN no draw with id 999
- WHEN `GET /draws/999` is called
- THEN the response is 404 with `{success:false, error:{code:"RESOURCE_NOT_FOUND"}}`.

### CD-08: Portability & Future Compatibility

F1 SHALL NOT prevent future rule changes or multi-bonus-ball lotteries [rule 1]: `super_number` is 0..1 today but SHALL be extensible to N via migration; lottery rule columns SHALL be extensible (nullable super range already); no hard-coded limits. The model SHALL use only portable constructs (REQ-05/REQ-09): no PG-only or SQLite-specific DDL [rule 4].

#### Scenario: multi-star is a forward-compatible migration
- GIVEN super_number UNIQUE(draw_id) today
- WHEN a second star is introduced (EuroMillions-style)
- THEN adding it requires only a migration (relaxing the UNIQUE), not a model rewrite.
