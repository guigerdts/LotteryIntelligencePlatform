# Exploration — Fase 0 Foundation: Base Architecture of Lottery Intelligence Platform

**Change**: `fase-0-foundation` — Create the base architecture of LIP: folder structure, main modules (data, features, analytics, models, backtesting, api, dashboard), entry point, and base configuration.
**Store**: openspec — this artifact: `openspec/changes/fase-0-foundation/exploration.md`
**Date**: 2026-08-05

---

## Current State

The repository is **documentation-only** (Fase 0 — Design & Architecture confirmed by README.md). Verified facts:

- No code scaffolding exists: no `pyproject.toml`, `requirements*.txt`, `package.json`, `*.py`, `vite.config`, or TS/JS sources anywhere (only `openspec/config.yaml`).
- Repo root contains the 10 authoritative design docs (README, CHARTER, SYSTEM_ARCHITECTURE, IMPLEMENTATION_ROADMAP, DATABASE_SCHEMA, API_SPECIFICATION, ENGINE_SPECIFICATIONS, FEATURE_ENGINEERING, LOTTERY_THEORY, SCIENTIFIC_METHODOLOGY) plus `openspec/` (init'd: `config.yaml`, empty `specs/`, empty `changes/archive/`).
- Git: single commit `446015d init: Lottery Intelligence Platform`; untracked `.codegraph/`, `.gga`. No `.gitignore`, no CI, no linter/test runner configured.
- OpenSpec SDD context already captured in `openspec/config.yaml` (stack, layered architecture, engines, Spanish docs / English artifacts, testing: none yet).

The roadmap defines Fase 0 — Foundation with explicit deliverables (repo structure, backend config, frontend config, SQLite config, configuration system, logging, env vars, dev scripts, project conventions) and acceptance criteria (backend starts, frontend starts, DB created, centralized config working). The foundation MUST anticipate Fases 1–19 (per the strict dependency chain and Definition of Done) without core modifications later.

## Affected Areas

- `backend/` — new. FastAPI app per SYSTEM_ARCHITECTURE.md §4; hosts all engines and layers.
- `frontend/` — new. React + Vite + Tailwind app per SYSTEM_ARCHITECTURE.md §4.
- `database/` — new. SQLite file location + migrations seed (schema arrives in Fase 1).
- `config/` or `backend/config/` — new. Centralized config system (config files + env vars) per §9/§12.
- `scripts/` — new. Dev scripts (run backend, run frontend, init db, seed env).
- `tests/`, `docs/`, `datasets/`, `experiments/`, `logs/` — new top-level placeholders.
- `.gitignore`, `README.md` (update), `pyproject.toml`/`requirements.txt`, `package.json` — new build/config files.
- `openspec/changes/fase-0-foundation/*` — SDD artifacts pipeline (this exploration, then proposal/spec/design/tasks).

## Proposed Structure (mapped from SYSTEM_ARCHITECTURE.md §4 + IMPLEMENTATION_ROADMAP Fase 0)

```
lip/
├── backend/
│   ├── app/                 # application layer root
│   │   ├── main.py          # FastAPI entry point
│   │   ├── api/             # v1 routers (per API_SPECIFICATION)
│   │   ├── core/            # config, logging, db session, security, deps
│   │   ├── config/          # settings loader (env + yaml/json)
│   │   ├── models/          # SQLAlchemy models (Fase 1)
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── repositories/    # data access (SQLite now, PostgreSQL later)
│   │   ├── services/        # application/business logic
│   │   ├── analytics/       # statistics + probability engines home
│   │   │   ├── statistics/
│   │   │   └── probability/
│   │   ├── ml/              # ML engine (Fase 7)
│   │   ├── dl/              # DL engine (Fase 8)
│   │   ├── optimization/    # Fase 9
│   │   ├── experiments/     # Fase 11
│   │   ├── generators/      # Fase 13
│   │   ├── backtesting/     # Fase 10
│   │   ├── simulations/     # Monte Carlo / simulator
│   │   ├── feature_engineering/  # Fase 4
│   │   ├── importers/       # Fase 2
│   │   ├── exporters/
│   │   └── utils/
│   ├── tests/               # or top-level tests/
│   └── requirements.txt / pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── components/
│   │   ├── charts/          # Plotly/ECharts wrappers
│   │   ├── hooks/
│   │   ├── services/        # API client (axios/fetch)
│   │   └── store/
│   ├── index.html, vite.config.js/ts, package.json, tailwind.config
├── database/                # SQLite file + migrations
├── docs/
├── datasets/
├── experiments/
├── tests/
├── scripts/
└── logs/
```

Module→Fase mapping used to justify placeholder breadth: importers(F2), statistics(F3), feature_engineering(F4), probability(F5), ml(F7), dl(F8), optimization(F9), backtesting(F10), experiments(F11), generators(F13), dashboard(F14), api(per API_SPECIFICATION), analytics(aggregator), models/repositories/services (F1 Core Domain).

## Approaches

1. **Minimal scaffolding (backend-only, empty engine packages)** — Create `backend/` with entry point, config system, logging, DB bootstrap; create all engine folders as empty packages with `__init__.py`; defer frontend to a stub `frontend/` README.
   - Pros: Fastest path to Fase 0 acceptance; zero risk of dead UI code; roadmap's frontend-heavy work arrives in Fases 14+.
   - Cons: Violates Fase 0 deliverable "Configuración del frontend" / acceptance "Frontend inicia correctamente"; the change name explicitly asks for the frontend module structure.
   - Effort: Low

2. **Full Fase 0 (backend + frontend scaffolds)** — Backend entry point + config + logging + SQLite init; frontend Vite+React+Tailwind scaffold with `src/pages/layouts/components/charts/hooks/services/store` placeholder structure and a healthy home page proxying to `/api/v1/health`.
   - Pros: Satisfies every Fase 0 deliverable and acceptance criterion; frontend structure exists before Fases 14+; single cohesive change.
   - Cons: Larger diff (review budget risk); Node toolchain added to a Python-focused repo; frontend placeholder pages may be throwaway.
   - Effort: Medium

3. **Backend now, frontend as a separate chained change** — Backend full Fase 0 here; frontend scaffold split into its own change (or its own task slice) to keep the diff reviewable.
   - Pros: Backend milestone lands fast and verified; keeps PR review budget in check (400-line guard).
   - Cons: Fase 0 acceptance "frontend inicia" is deferred, so the phase is only partially "done" per roadmap DoD; requires orchestrator to manage two-phase sequencing.
   - Effort: Medium (split)

**Recommendation**: **Approach 2 — full Fase 0** — the change name explicitly includes the frontend module structure, and Fase 0's acceptance criteria include frontend startup and DB creation. However, scaffold frontend as Vite+React+Tailwind with the documented `src/` structure and a minimal home page wired to `/api/v1/health` — do NOT build dashboard pages (Fase 14). Use chained/slice planning in sdd-tasks if the forecast exceeds the 400-line budget (e.g., backend slice → frontend slice).

## Entry Point + Configuration (#1)

- **Backend entry**: `backend/app/main.py` — FastAPI app factory; mounts `app.api.v1` router under `/api/v1` per API_SPECIFICATION.md; `/health` and `/version` endpoints (API_SPECIFICATION §16); CORS for the Vite dev server; JSON logging bootstrap on startup; DB engine creation (SQLite path from config) without schema migration in Fase 0 (schema is Fase 1).
- **Centralized config**: layered resolution — defaults (embedded/base YAML) → env vars (`pydantic-settings` or `python-dotenv` + dataclass) → overrides. Secrets via `.env` only (SYSTEM_ARCHITECTURE §12). Config sections anticipated: app (name/version/env), api (host/port/cors), database (url/dialect), logging (level/formats), lotteries registry placeholder (rules live outside code per §9/§11 — actual registry in Fase 1/2), experiments (seed defaults), paths (datasets/logs/models dirs).
- **Logging bootstrap**: `app/core/logging.py` — stdlib `logging` configured at startup, JSON-ish structured format, per-module logger names mirroring package paths; observability contract per §10 (logs, errors, timing, resource usage).

## Inconsistencies / Gaps (Fase 0 relevant, not to over-engineer)

1. **§4 folder list vs layered architecture**: SYSTEM_ARCHITECTURE §4 lists flat engine folders (`statistics/`, `probability/`, `ml/`, `dl/`) while §3 defines Presentation/API/Application/Domain/Data layers. The flat list omits layer anchors (`domain/`, `application/`) that §3 implies. Gap: decide mapping — engines live under `backend/app/<engine>` (cohesive with §4) and layers are expressed via `api/`, `services/`, `repositories/`, `models/` (cohesive with §3). Document this mapping in the design phase; do not invent a `domain/` tree in Fase 0.
2. **`analytics/` vs `statistics/`+`probability/` overlap**: §4 lists all three. Recommend `analytics/` as the orchestration layer that composes `statistics/` + `probability/` results, or drop `analytics/` and keep engines direct. Decision needed at design time; placeholder both is acceptable for Fase 0.
3. **Frontend/backend toolchain unspecified**: docs name React+Vite+Tailwind but not JS/TS, package manager, or Python version/packaging tool. Choose and pin (recommend: Python ≥3.11 + `uv` or pip-tools; TypeScript for Vite app; single `package-lock`/`pnpm-lock`). Flag to user as a decision.
4. **Fase 0 DoD vs scope creep**: roadmap Fase 0 includes "Base de datos creada" and "Frontend inicia correctamente" — DB *creation* is in scope (SQLite file + engine), but schema/migrations are Fase 1; frontend "starts" means scaffold boots, not pages built. State this boundary explicitly in proposal.
5. **SQLite→PostgreSQL path**: DATABASE_SCHEMA mandates PostgreSQL-compatible design (3NF, FKs, indices). Fase 0 must not hard-code SQLite-specific code paths in repositories; DB access stays behind `repositories/` + SQLAlchemy ORM (or SQLModel) so dialect swap is config-only (Fase 1+).
6. **API envelope + base URL**: API_SPECIFICATION requires `/api/v1` prefix and a `{success, data/meta | error, timestamp}` envelope. Entry-point router mounting and an exception handler must be in Fase 0 scaffolding so all future endpoints inherit it.
7. **Docs language vs artifact language**: docs are Spanish; SDD technical artifacts stay English per `openspec/config.yaml` context. Naming of packages/dirs is English (per §4) — keep code identifiers English.

## Risks

- **Scope inflation**: frontend + DB + config + logging in one change grows the diff; mitigate with sdd-tasks slicing (chained PRs) if the 400-line budget forecast is high.
- **Throwaway scaffolding**: placeholder pages/folders may be rewritten in Fases 14+/engine phases; acceptable if structure matches §4 exactly (docs are the contract).
- **Toolchain lock-in**: choosing uv/pip vs poetry and TS vs JS is user-facing; wrong guess causes churn — surface as an explicit decision in the proposal rather than assuming.
- **SQLite→PostgreSQL migration**: if repositories bypass the ORM/repository boundary in Fase 0 helpers, future migration cost rises; enforce the boundary now.
- **No test runner yet**: config.yaml has `tdd: false`; Fase 0 should still add a minimal smoke test (app import + /health) and enable pytest, else phase 17 (≥80% coverage) starts from zero with no harness.
- **Config layering drift**: if env vars and YAML defaults diverge across modules, centralized-config principle (SYSTEM_ARCHITECTURE §9) erodes; single `settings` object must be the only config access point.

## Ready for Proposal

**Yes.** Exploration complete: repo state confirmed (docs-only, openspec initialized), module tree mapped to §4 + roadmap Fases, entry point/config/logging approach defined, inconsistencies and risks catalogued. Orchestrator should tell the user the change is scoped to full Fase 0 (backend + frontend scaffolds + config + logging + SQLite init) with two open decisions to confirm in proposal: (a) Python packaging tool (uv/pip-tools/poetry) and frontend TS vs JS; (b) whether frontend scaffold is part of this change or a chained slice.
