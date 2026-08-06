# Design — Fase 0 Foundation: Backend Base Architecture

**Change**: `fase-0-foundation` · **Store**: `openspec` · **Date**: 2026-08-05

## Technical Approach

Backend-only layered FastAPI scaffold. The package tree under `backend/app/` mirrors `SYSTEM_ARCHITECTURE.md §4` exactly, with §3 layer anchors surfaced as `api/`, `services/`, `repositories/`, `models/` — no invented `domain/` tree. `analytics/` composes `statistics/` + `probability/` (user-confirmed upstream decision). All engines exist as empty interface-bearing seams (docstring only). Config is a single deterministic pydantic-settings object; SQLite bootstrap is dialect-driven behind an ORM boundary; stdlib logging; ruff + pre-commit + pytest green. **No business/engine logic, no schema, no frontend.**

Package count: 22 packages (SEED list below) — `main` is a module, not a package.

## Project Layout

```
/root/LotteryIntelligencePlatform/
├── backend/
│   ├── app/           # src-layout package (import path `backend.app`)
│   │   ├── main.py, api/, core/, config/, models/, schemas/,
│   │   │   repositories/, services/, analytics/, statistics/,
│   │   │   probability/, feature_engineering/, ml/, dl/, generators/,
│   │   │   backtesting/, experiments/, optimization/, simulations/,
│   │   │   importers/, exporters/, utils/
│   └── pyproject.toml
├── config/.env.example
├── scripts/           # run_backend.sh, init_db.sh
├── tests/             # smoke test
├── database/          # SQLite file location
├── .gitignore, .pre-commit-config.yaml, README.md
```
Root-level `tests/` and `config/` per §4; `pyproject.toml` lives **in `backend/`** (see decisions).

### Decision table

| Decision | Option / tradeoff | Choice |
|---|---|---|
| src-layout vs flat | src-layout hides internals, robust `import backend.app`; flat simpler but pollutes PATH | **src-layout** — mirror §4; `backend/` as package root, `app/`=fastapi layer. `[tool.uv]`/wheel installs the `backend` package |
| `pyproject.toml` at root vs `backend/` | root conflates tools for both backend+future frontend | **in `backend/`** — Python tooling self-contained; `uv run --project backend` / `uv run --directory backend` |
| `uv` dep mgmt | venv auto-created; `uv.lock` pins exact versions (reproducibility REQ-08) | **uv** user-confirmed; `uv add fastapi 'uvicorn[standard]' pydantic pydantic-settings sqlalchemy pytest httpx ruff pre-commit` |
| `analytics/` | separate package composing two engines vs drop it | **composition layer** — re-exports/orchestrates `statistics.ProbabilityService`; downstream reads only `analytics` |
| DB dialect | SQLite now, PostgreSQL later | **config-only** via `database.url`; repositories consume `Session`/`engine` only (no SQLite-isms) |

## Package Seams

| Package | Responsibility (docstring only) |
|---|---|
| `api` | v1 routers; mounts under `/api/v1` |
| `core` | logging, exceptions, app-factory helpers |
| `config` | pydantic-settings `Settings` singleton |
| `models` | SQLAlchemy ORM entities (Fase 1) |
| `schemas` | Pydantic request/response + envelope schemas |
| `repositories` | data-access boundary; base repo + ORM session/engine |
| `services` | application/business logic layer |
| `analytics` | **composition layer** over `statistics` + `probability` |
| `statistics` | Descriptive/statistical metrics engine |
| `probability` | Probabilistic models engine (Monte Carlo, Bayes…) |
| `feature_engineering` | Derived variable computation engine |
| `ml` / `dl` | Classical / neural model engines (Fases 7–8) |
| `optimization` | GA/PSO/SA/Bayesian optimization (Fase 9) |
| `backtesting` | Walk-forward validation engine (Fase 10) |
| `experiments` | Experiment orchestration engine (Fase 11) |
| `generators` | Combination generator engine (Fase 13) |
| `simulations` | Monte Carlo / simulation runtime |
| `importers` / `exporters` | Data import / export (Fase 2) |
| `utils` | Shared helpers |

## Architecture: app factory, Config, Logging, DB

**Data flow (startup):**

```
create_app()
  ├─ bootstrap logging (core/logging.py)
  ├─ build Engine from settings.database.url (core/db.py)
  ├─ add CORS (Vite dev origin, defaults=['http://localhost:5173'])
  ├─ mount api_router → /api/v1 (health+version)
  ├─ add envelope exception handler
  └─ return App
uvicorn backend.app.main:create_app()
```

- **App factory** `main.create_app()`: `FastAPI(lifespan=...)`; startup logs configured level; mounts `api_v1_router` under `/api/v1`; `GET /health` → `{success,data:{status:"ok"},timestamp}` and `GET /version` → `{success,data:{version,app},timestamp}` (ISO 8601 UTC). Global handler maps `HTTPException`, validation errors, and unhandled → `{success:false,error:{code,message},timestamp}`.
- **Config** (`config/settings.py`): pydantic-settings v2 `Settings`, `model_config = SettingsConfigDict(env_prefix="LIP_", env_file=".env")`. Sections: `app`(name/version/env), `api`(host/port/cors), `database`(url, dialect derived), `logging`(level, format), `paths`(database/logs/models). Precedence: class defaults → `.env`/env. Module-level lazy singleton `get_settings()` (cached); secrets via env only.
- **Logging** (`core/logging.py`): stdlib `logging`, `configure_logging(level)` → named formatter `%(asctime)s|%(levelname)s|%(name)s|%(message)s`; per-module `logging.getLogger(f"backend.app.{module}")` mirrors paths; level from `settings.logging.level`. No external lib.
- **DB bootstrap** (`core/db.py`, `scripts/init_db.sh`): SQLAlchemy `create_engine(settings.database.url)` (SQLite path → `database/lip.db`). `init_db()` creates empty file; **no tables/metadata.create_all** (`Base.metadata.create_all` deferred to Fase 1 migrations). `repositories/base.py` defines `Base` declarative + session factory stub; engine built dialect-driven config `url`.

## Testing Strategy

| Layer | What | Approach |
|---|---|
| Smoke | `/api/v1/health` → 200 envelope; `/version` valid; TestClient (httpx) on in-process app | `tests/test_smoke.py` in `backend/tests/` |
| Env override | `LIP_APP_NAME` override + unset fallback | `tests/test_config.py` |
| Tooling | `ruff check` + `ruff format --check` pass; pytest passes | `[tool.pytest.ini_options] pythonpath = ["."]` |

`[tool.pytest.ini_options] sets `testpaths`, `pythonpath=["."]` so `import backend.app` works; `smoke` uses `TestClient` (lighter than LiveServer for `/health`).

## Tooling / Scripts / Hygiene

- `[tool.ruff] line-length=100; lint select=["E","F","I","UP","B"]; format default`. pre-commit: `ruff` (check) + `ruff-format`.
- `scripts/run_backend.sh` → `uv run uvicorn backend.app.main:create_app --reload`; `scripts/init_db.sh` → creates SQLite path dir + empty DB.
- `.gitignore`: `__pycache__/`, `.venv/`, `.env`, `*.db*`, `.ruff_cache/`, `.pytest_cache/`, `/database/` (repo-root DB dir per §layout; matches `settings.py` default `database_dir` = repo-root `database/`). `.env.example` without secrets. README documents layout + engine seams + config precedence.

## Migration / Rollout

State-machine of Fase 1 revisions (per roadmap): Fase 1 introduces schema + migrations (`alembic` recommended); Fase 14 wires `/dashboard`. Fase 0 is additive scaffold only; **kernel migration** = future. No data migration now. Rollback: revert foundation commit; DB file is recreated on boot.

## Open Questions

- None blocking. (Aliasing of `statistics`→`statistics_engine` vs `statistics` package name resolves at Fase 3 implementation time.)

## Threat Matrix — not applicable

`N/A — no routing/shell/subprocess/VCS-PR/executable-file-classification/process-integration boundary in this scaffold change` (all design-time seams, no execution boundary).

## Contract

**Status**: `proposed`. Next: `sdd-tasks`.