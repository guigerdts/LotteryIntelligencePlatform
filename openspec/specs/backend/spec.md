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

**Next**: `sdd-design` (module seams/contracts). **Note**: this is a new foundation spec; per OpenSpec it would land in a domain subfolder at archive; the task directs it to `spec.md` root — recorded here for provenance.