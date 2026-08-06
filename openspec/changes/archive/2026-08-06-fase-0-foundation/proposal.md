# Proposal — Fase 0 Foundation: Backend Base Architecture

**Change**: `fase-0-foundation` · **Store**: `openspec` · **Date**: 2026-08-05
**Status**: proposal — ready for user review

## Executive Summary

Create the minimal **backend-first** skeleton of Lottery Intelligence Platform: a layered, module-modular FastAPI project whose folder and package seams mirror `SYSTEM_ARCHITECTURE.md §4` exactly — so Fases 1–19 land into a fixed structure with no core rework. This change ships folder/package scaffolding, a FastAPI entry point with `/health`, a single centralized config source of truth, structured logging bootstrap, SQLite DB creation, and passing pytest smoke test. **No engine logic.**

## Intent

Build a runnable foundation — currently the repo is documentation-only. The outcome: `backend` boots, config loads centrally, an empty SQLite DB is created, `/api/v1/health` returns success, and `pytest` passes a smoke test.

## Business / Technical Problem

Repo has no code (no `pyproject.toml`, no `*.py`), so Fase 0 acceptance is unmet. The foundation must anticipate Fases 1–19 (see `IMPLEMENTATION_ROADMAP.md` Dependency Chain + DoD) without later core modifications.

## Scope — In (backend foundation only)

- **Folder/package tree** under `backend/app/`: `main`, `api`, `core`, `config`, `models`, `schemas`, `repositories`, `services`, `analytics`, `statistics`, `probability`, `feature_engineering`, `ml`, `dl`, `generators`, `backtesting`, `experiments`, `optimization`, `simulations`, `importers`, `exporters`, `utils`. **Empty / interface packages only** (`__init__.py`), no algorithms.
- **FastAPI entry point** `backend/app/main.py`: app factory; mounts `api/v1` under `/api/v1`; `/health` + `/version` endpoints; CORS for the Vite dev server; global exception handler returning the `{success, data|error, timestamp}` envelope (per `API_SPECIFICATION.md`).
- **Centralized config** (`config/`): layered defaults → env overrides via `pydantic-settings`; single `settings` object is the only access point; sections `app`, `api`, `database`, `logging`, `paths`; secrets via `.env` only (§9/§12).
- **Logging bootstrap** (`core/logging.py`): stdlib `logging`, JSON-ish structured format, per-module loggers mirroring package paths.
- **SQLite bootstrap**: create the DB file (path from config) — **no schema/migrations** (Fase 1).
- **`uv` packaging**: `pyproject.toml`; `backend` package install.
- **Code quality tooling from Fase 0**: `ruff` as linter AND formatter (replaces Black + isort + flake8); `pre-commit` hooks wired (ruff check, ruff format check) to guarantee code quality from day one.
- **pytest + smoke test** (app imports, `/health` returns expected envelope).
- **Dev scripts** (`scripts/`): run backend, init DB; `.gitignore`; `README.md` updated with structure/conventions.
- SDD artifacts pipeline for this change (exploration done; proposal, then spec/design/tasks/apply/verify).

## Scope — Out (non-goals)

- **Frontend (React+Vite+Tailwind) scaffold** — deferred to a **separate chained slice**. Reference this boundary now; the scaffold ships as a chained PR after this change.
- Actual engine algorithms / statistics / probability / feature / ML / backtesting / generator logic — empty seams only.
- Schema / migrations / core-domain entities (Fase 1).
- Dashboard pages (Fase 14), generator UI, auth, PostgreSQL.

## Approach & Alternatives

- **Chosen**: layered monolith-as-modules — one `backend/` package where `api`/`services`/`repositories`/`models` express §3 layering anchors and engines (`statistics`, `probability`, `ml`, ...) are sibling packages per §4. `analytics/` acts as the composition layer over `statistics` + `probability`. No separate `domain/` tree.
- **Alternative (flat)**: `backend/` root kept engine folders flat. Rejected: loses the §3 layer anchors.
- **Alternative (pip / poetry)**: rejected — `uv` user-confirmed.
- **Alternative (frontend in this change)**: rejected — splits into a chained slice to keep the diff reviewable.

## Assumptions (explicit)

**User-confirmed**
- Packaging tool = `uv` (`pyproject.toml`).
- Backend-first; frontend scaffold ships as a **separate chained slice**, NOT in this change.
- `analytics/` = composition layer over `statistics/` + `probability/` (design-time decision).
- SQLite→PostgreSQL safety via `repositories/` + SQLAlchemy ORM boundary from day one (dialect swap = config-only).
- **Python `>=3.12`** (3.13 only if every critical dependency confirms compatibility — NOT Python 4.x, which has no stable release).
- **Pydantic `v2.x`** with a **FastAPI version compatible with Pydantic v2**.
- **Ruff** as linter + formatter, **pre-commit hooks** from Fase 0 (code-quality debt prevention).

**Inferred (flagged for confirmation)**
- None outstanding — toolchain versions now confirmed above. Exact patch pins (e.g. `fastapi>=0.111`, `pydantic>=2.6`) to be fixed during the spec phase if needed.

## Requirements / Deliverables (spec phase fleshes out)

- **Entry point**: app factory, router mounting, `/health`/`/version`, exception-envelope handler, startup logging.
- **Config layering**: resolution precedence MUST be deterministic (defaults→env); single `settings`.
- **Module seams**: exact package list + what (empty) each contains; engine registry placeholder.
- **Logging**: bootstrap config contract.
- **DB**: SQLite engine/create bound to build; no migration.
- **Smoke test**: succeeds on clean test env.

## Acceptance Criteria (this change — backend foundation)

- [ ] `uv run uvicorn backend.app.main` boots without error
- [ ] Centralized config loads from `.env` + defaults; single settings object used everywhere
- [ ] SQLite DB file created at configured path (empty, no schema)
- [ ] `ruff check` + `ruff format --check` pass on the scaffold; `pre-commit` hooks installed and green (`ruff` pre-commit hooks)
- [ ] `GET /api/v1/health` returns 200 with success envelope; `/version` present
- [ ] `pytest` passes smoke test(s)

> **Frontend acceptance explicitly NOT in this change** — resolved by the chained frontend slice (its own milestone).

## Risks (camelCase following)

- **ScopeInflation**: frontend/DB/config/logging pulled into one change grows diff. Mitigate: frontend split out above; enforce the 400-line guard in sdd-tasks (chained PRs if forecast high).
- **ThrowawayScaffold**: empty packages/placeholders may be rewritten in Fases 14+. Mitigate: structure matches §4 exactly — docs are the contract.
- **EnginePackagesDrift**: engine dirs drift before design (Fase 3+). Mitigate: keep them empty-interface; design phase adds contracts.
- **RepositorySchemeBoundary**: Fase 0 helpers hard-coding SQLite-isms raises PostgreSQL migration cost. Mitigate: all DB access behind `repositories/` + ORM.
- **ToolchainLockIn**: wrong Python/pydantic pin causes churn. Mitigate: `>=3.12` + `pydantic v2` user-confirmed; ruff+pre-commit enforce consistency from Fase 0.

## Rollback Plan

- All this phase creates code/config/DB-file assets; no migration touches production.
- Remove the `backend/`, `config/`, `scripts/` scaffolding (git clean `git clean`/revert the foundation commit); DB is a generated artifact that can be deleted (recreated on next boot).

## Dependencies

- `uv` (user-side), Python ≥3.12 runtime (3.13 only if dependency-compatible), any prior artifacts in `openspec/changes/fase-0-foundation/` (exploration read).
- None hard — foundation has no internal deps.

## Success Criteria

- [ ] Workspace boots backend; all acceptance criteria above green.
- [ ] Fase 0 (backend portion) complete per `IMPLEMENTATION_ROADMAP.md` DoD; frontend acceptance deferred to its chained slice.
- [ ] Foundation is reproducible and traceable (conventional-commits history, no secrets committed).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/**` | New | Modules+entry point per scope |
| `config/` | New | Centralized settings |
| `scripts/` | New | Dev scripts (run backend, init db) |
| `pyproject.toml` | New | Build/config files, `ruff` + `pytest` config, dev deps |
| `.pre-commit-config.yaml`, `ruff` config | New | Fase 0 code-quality hooks (replaces Black/isort/flake8) |
| `tests/` | New | pytest smoke test |
| `.gitignore`, `pyproject.toml` | New | Build/config files |
| `README.md` | Modified | Structure + conventions |
| `openspec/changes/fase-0-foundation/*` | Modified/New | SDD artifacts |

---

**Next**: `sdd-spec` (requirements) then `sdd-design` (module seams/contracts).