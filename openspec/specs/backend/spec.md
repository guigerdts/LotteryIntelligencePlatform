# Spec — Fase 0 Foundation: Backend Base Architecture

**Change**: `fase-0-foundation` · **Store**: `openspec` · **Date**: 2026-08-05
**Artifact**: spec (this change) — new foundation domain, no prior main spec.

## Purpose

Define the backend-only foundation of Lottery Intelligence Platform: a layered FastAPI scaffold whose folder and package seams mirror `SYSTEM_ARCHITECTURE.md §4`, a single centralized config source of truth, structured logging, SQLite bootstrap (engine only, **no schema), and code-quality tooling. **No business/engine logic.** All engine algorithms, schema entities, and the frontend scaffold are explicitly out of scope (later fases / chained frontend slice).

## Requirements

| ID | Requirement | Strength |
|----|-------------|----------|
| REQ-01 | Folder & package tree under `backend/app/` | MUST |
| REQ-02 | FastAPI entry point + envelope + `/health`/`/version` | MUST |
| REQ-03 | Centralized configuration | MUST |
| REQ-04 | Logging bootstrap | MUST |
| REQ-05 | SQLite bootstrap & schema ownership | MUST |
| REQ-06 | Tooling: ruff, pre-commit, pytest | MUST |
| REQ-07 | Dev scripts & repo hygiene | MUST |
| REQ-08 | Non-functional: reproducible, no business logic, chained-frontend out of scope | MUST |
| REQ-09 | Alembic migration ownership | MUST |
| REQ-10 | Manual stats generation endpoint (`POST /statistics/generate`) | MUST |
| REQ-11 | Separate read endpoints, no precompute (`GET /statistics/...`) | MUST |
| REQ-12 | CLI manual trigger for stats generation | MUST |

### REQ-01: Folder & Package Tree

The backend SHALL ship the package tree under `backend/app/` — `main`, `api`, `core`, `config`, `models`, `schemas`, `repositories`, `services`, `analytics`, `statistics`, `probability`, `feature_engineering`, `ml`, `dl`, `generators`, `backtesting`, `experiments`, `optimization`, `simulations`, `importers`, `exporters`, `utils`.

- Each sibling package SHALL be an empty seam (`__init__.py` only) asserting a `docstring` of its future responsibility.
- `analytics/` SHALL assert it is the composition layer over `statistics/` + `probability/`.
- The repo SHALL provide `backend/`, `config/`, `scripts/`, `tests/`, `.gitignore`, `pyproject.toml`, `.pre-commit-config.yaml`, `.env.example` and a ruff config (`[tool.ruff]` in `pyproject.toml`).

**Acceptance**
- [ ] All 22 packages exist under `backend/app/`, each with `__init__.py` and responsibility docstring, none with logic.
- [ ] Exact §4 folder names; no invented `domain/` tree.

### REQ-02: FastAPI Entry Point & Response Envelope

`backend/app/main.py` SHALL expose an app factory returning a FastAPI app. It SHALL mount `api/v1` under `/api/v1`, and `GET /health` and `/version` per `API_SPECIFICATION.md §16. Every response SHALL use the envelope `{success, data|error, timestamp}`. InputValidationError, HTTPException, and unhandled exceptions SHALL map to the envelope via a global handler. CORS MUST allow the Vite dev origin.

**Acceptance**
- [ ] `GET /api/v1/health → 200 with `success:true` envelope; `/version` present.
- [ ] Envelope shape + error envelope for error paths per spec; `timestamp` ISO 8601 UTC.

#### Scenario: health success
- GIVEN an app started with default config
- WHEN a client calls `GET /api/v1/health`
- THEN the response is 200 with `{success:true, data, timestamp}` and a valid `/version`.

### REQ-03: Centralized Configuration

A single `settings` pydantic v2 (pydantic-settings) object SHALL be the only access point. Precedence MUST be deterministic: built-in section defaults (app/api/database/logging/paths) → `.env`/environment overrides. Secrets MUST come only from env/`.env`, never code. Distinct access paths MUST NOT be introduced.

**Acceptance**
- [ ] `settings` singleton used everywhere; precedence defaults-first enforced in a smoke scenario/env test. env override respected.
- [ ] No hard-coded secrets in source.

#### Scenario: env overrides default
- GIVEN a default `app.name` and an env var `APP_NAME=lip-dev`
- WHEN `settings` is resolved
- THEN `settings.app.name == "lip-dev"`; unset vars fall back to defaults.

### REQ-04: Logging Bootstrap

`core/logging.py` bootstraps stdlib `logging` at startup with a structured format, per-module logger names mirroring package paths, and a level configurable from settings.

**Acceptance**
- [ ] Startup emits a log line in the structured format at the configured level; `logging.getLogger("backend.app...")` names track package paths.

#### Scenario: configured level honored
- GIVEN `settings.logging.level = DEBUG`
- WHEN the app starts
- THEN debug records are emitted; the setting drives the emitted level.

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

### REQ-06: Code-Quality Tooling

`ruff` SHALL be the single linter and formatter (`[tool.ruff]`, line-length 100); `ruff check` and `ruff format --check` MUST pass on the scaffold. `.pre-commit-config.yaml` MUST wire ruff (check + format) hooks that pass on the empty tree. pytest SHALL be enabled; a smoke test MUST import the app and assert `/health` returns the envelope 200.

**Acceptance**
- [ ] `uv run ruff check .` and `ruff format --check .` pass; `pre-commit run --all-files` green.
- [ ] `pytest` passes a smoke test asserting `/api/v1/health` returns 200 envelope.

### REQ-07: Dev Scripts & Repo Hygiene

scripts/ SHALL provide run-backend + init-DB entries (`run_backend.sh`, `init_db.sh` or equivalent). `.gitignore` SHALL cover Python/uv/SQLite artifacts. `README.md` SHALL be updated with structure and conventions. No secrets SHALL be committed.

**Acceptance**
- [ ] `scripts/run_backend.sh` boots the backend; `scripts/init_db.sh` creates the DB; `.env.example` present with no real secrets.
- [ ] `.gitignore` ignores `__pycache__`, `.venv`, `.env`, `*.db`/SQLite artifacts; `README.md` documents structure + conventions.

### REQ-08: Non-Functional & Boundaries

Fase 0 SHALL be reproducible (exact pins via `uv.lock`) and SHALL contain no business/engine logic beyond empty seams. The frontend scaffold and all engine algorithms SHALL be recorded as explicitly out-of-scope here (chained frontend slice; later fases). Definition-of-Done acceptance per `IMPLEMENTATION_ROADMAP.md`.

**Acceptance**
- [ ] `uv.lock` present; reproducibility via declared pins.
- [ ] No engine algorithm, schema entity, or frontend code lands in this change; boundary documented.

### REQ-09: Alembic Migration Ownership

Alembic (`backend/alembic/`, `env.py` → `target_metadata = Base.metadata`) SHALL be the sole schema owner [D10]. Migrations SHALL use only portable operations (`batch_mode` for SQLite DDL); PG-specific or SQLite-specific DDL MUST NOT be introduced. `init_db` SHALL NOT create schema.

#### Scenario: migrations create the F1 schema
- GIVEN a fresh DB file created by `init_db`
- WHEN `alembic upgrade head` runs
- THEN tables `lottery`, `draw`, `draw_numbers`, `super_number`, `datasets`, `dataset_draws` exist with their constraints.

---

## Requirements Added by `fase-3-statistics` (2026-08-07)

> Delta merged at archive. All behavior follows the statistics-engine STE-01..13 contract. Read/write separation (C5), read-only re core tables (C3), and out-of-scope rules are owned by statistics-engine (STE-02/05/10/13); backend re-exposes them through these API/CLI seams.

### REQ-10: Manual Generation Endpoint

`POST /statistics/generate` SHALL trigger snapshot generation/update on demand (C5, D6) and MUST NOT overlap `GET /statistics/...`. The request SHALL identify the lottery (`lottery_id` or code) and an optional bounded scope; the response SHALL be the envelope. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); generation failure SHALL return `generation_error` (500). The endpoint SHALL never fire during import.

`POST /ml/train` SHALL additionally trigger ML snapshot training on demand (MLE-09), with request fields `lottery_id|code`, `model_set` (`core-5` default), and optional `cut` for the walk-forward window. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); a training failure SHALL return `training_error` (500); a leakage-invalid split SHALL be rejected. `POST /ml/train` MUST NOT overlap `GET /ml/models` or `GET /ml/metrics` and SHALL never fire during import.

`POST /dl/train` SHALL additionally trigger DL snapshot training on demand (DLE-14), with request fields `lottery_id|code`, `model_set` (`core-3` default), optional `window` (`W`, default 10, bounds 2..20), and optional `cut` for the window-aware split. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); below the 100-real-draw floor the response SHALL be a clean `INSUFFICIENT_DATA` (DLE-10); a leakage-invalid (straddling/shuffled) split SHALL be rejected (DLE-05); a training failure SHALL return `training_error` (500). `POST /dl/train` MUST NOT overlap the GETs and SHALL never fire during import.

#### Scenario: generation is manual only

- GIVEN a configured lottery and a running app
- WHEN `POST /statistics/generate` is called
- THEN a `stat_*` snapshot is produced (incremental over an existing valid snapshot, full otherwise per C4) and the response is the 200 envelope.

#### Scenario: unknown lottery maps to 404

- GIVEN a running app
- WHEN `POST /statistics/generate` targets an unknown lottery
- THEN the response is 404 `{code:"RESOURCE_NOT_FOUND"}` and no snapshot is written.

#### Scenario: ml train is manual and scoped

- GIVEN a configured lottery with F4 features and draws ≥ `cut`
- WHEN `POST /ml/train {model_set:"core-5"}` is called
- THEN an `ml_*` snapshot version is produced (idempotent per MLE-08) and the response is the 200 envelope; the run never overlaps reads.

#### Scenario: dl train is manual, scoped, and floored

- GIVEN a configured lottery with ≥100 real draws and F4 features
- WHEN `POST /dl/train {model_set:"core-3", window:10}` is called
- THEN a `dl_*` snapshot version is produced (idempotent per DLE-12) and the response is the 200 envelope; never overlapping reads.

#### Scenario: dl train refuses below the data floor

- GIVEN a lottery with fewer than 100 real draws
- WHEN `POST /dl/train` is called
- THEN the response is a clean `INSUFFICIENT_DATA` and no `dl_*` snapshot or weights are written.

### REQ-11: Separate Read Endpoints, No Precompute

`GET /statistics/...` SHALL serve reads only and MUST NOT trigger automatic precompute (C5). Point queries and small windows (LAST N, bounded filters) SHALL be answered on demand (D1) against existing snapshots; a MISSING snapshot SHALL surface a resolution error rather than silently precompute.

`GET /ml/models` SHALL list the model registry (executed + `future-ml` families per MLE-07) for a lottery and `GET /ml/metrics` SHALL return a lottery's active metrics — both read ONLY the stored `ml_*` snapshot and MUST NOT trigger training. A missing `ml_*` snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404).

`GET /dl/models` SHALL list the DL model registry (executed + `future-dl` families per DLE-11) for a lottery and `GET /dl/metrics` SHALL return a lottery's active DL metrics — both read ONLY the stored `dl_*` snapshot and MUST NOT trigger training. A missing `dl_*` snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404). No `GET` SHALL expose model weights; `/dl/predict` and ranking/recommendation surfaces SHALL NOT be registered (DLE-14).

#### Scenario: read does not precompute

- GIVEN a valid snapshot for a lottery
- WHEN `GET /statistics/{lottery}/frequencies?last=10` runs
- THEN it returns the bounded on-demand result and no generation occurs.

#### Scenario: missing snapshot signals, not computes

- GIVEN a lottery with no snapshot
- WHEN a read targets it
- THEN the response signals the absence (error) and does NOT trigger generation.

#### Scenario: ml reads never train

- GIVEN a lottery without an `ml_*` snapshot
- WHEN `GET /ml/metrics` targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and `POST /ml/train` is never fired.

#### Scenario: dl reads never train

- GIVEN a lottery without a `dl_*` snapshot
- WHEN `GET /dl/metrics` targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and `POST /dl/train` is never fired.

#### Scenario: dl routes are limited to train/models/metrics

- GIVEN the API router after F8
- WHEN route discovery runs
- THEN only `POST /dl/train`, `GET /dl/models`, `GET /dl/metrics` are registered; `/dl/predict`, ranking, and weights-download routes do not exist.

### REQ-12: CLI Manual Trigger

The CLI (`cli.py`) SHALL expose a manual generation/update command matching the API (D6), accepting lottery scope and optional bounded-window configuration. The run's trigger SHALL be recorded as manual/CLI.

CLI parity SHALL add `lip ml train|models|metrics`: `lip ml train` mirrors `POST /ml/train` (same lottery/`model_set`/`cut` options), `lip ml models` and `lip ml metrics` mirror the reads, printing the same snapshot data.

CLI parity SHALL add `lip dl train|models|metrics`: `lip dl train` mirrors `POST /dl/train` (same lottery/`model_set`/`window`/`cut` options and floor behavior), `lip dl models` and `lip dl metrics` mirror the reads, printing the same snapshot data. No CLI predict/export/weights command SHALL be added.

#### Scenario: CLI generates snapshot

- GIVEN a CLI invocation for a lottery
- WHEN the command runs
- THEN a snapshot is generated (incremental/full per C4), reported, and no import hook fires.

#### Scenario: CLI trains ml snapshot

- GIVEN a CLI invocation with a lottery and `model_set=core-5`
- WHEN `lip ml train` runs
- THEN an `ml_*` snapshot is produced or reported idempotent, and reads (`lip ml metrics`) print stored rows without training.

#### Scenario: CLI trains dl snapshot

- GIVEN a CLI invocation with a lottery and `model_set=core-3`
- WHEN `lip dl train` runs
- THEN a `dl_*` snapshot is produced or reported idempotent (or `INSUFFICIENT_DATA` below the floor), and reads (`lip dl metrics`) print stored rows without training.

---

**Next**: `sdd-design` (module seams/contracts). **Note**: this is a new foundation spec; per OpenSpec it would land in a domain subfolder at archive; the task directs it to `spec.md` root — recorded here for provenance.