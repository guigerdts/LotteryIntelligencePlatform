# Tasks: Fase 0 Foundation — Backend Base Architecture

**Change**: `fase-0-foundation` · **Store**: `openspec` · **Date**: 2026-08-05
**Boundary**: Backend infrastructure + scaffolding ONLY. No business/engine logic, no schema/migrations, no frontend (deferred chained slice).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~850–1000 (scaffold + tooling + config + tests) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 3 chained work units (below) |
| Delivery strategy | ask-on-risk |

```text
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High
```

**Rationale**: Empty seam `__init__.py` files are cheap, but pyproject + ruff/pre-commit + pydantic-settings + envelope + SQLAlchemy engine + app factory + tests + scripts + README exceed 400 changed lines. Split so each work-unit stays under the budget and infra stays separate from functionality:

- **WU-1 (PR-1, infra, ~320)**: Tasks 1, 2, 11 — uv project, package tree, ruff+pre-commit. Rollback: revert commit; no app routes.
- **WU-2 (PR-2, core/config, ~350)**: Tasks 3, 4, 5, 6, 7 — settings, logging, db/repositories, envelope, api router. Rollback: revert PR-2; seams unaffected.
- **WU-3 (PR-3, wiring, ~330)**: Tasks 8, 9, 10, 12, 13 — app factory, scripts, hygiene, tests, README. Rollback: revert PR-3.

> **Correctness check — REQ-01**: "22 packages" = **21 empty seam packages** (api, core, config, models, schemas, repositories, services, analytics, statistics, probability, feature_engineering, ml, dl, generators, backtesting, experiments, optimization, simulations, importers, exporters, utils) **+ `main.py` as a MODULE** (not a package). `analytics/` docstring MUST assert composition over `statistics`+`probability`. No invented `domain/` tree.

## Task Summary Table

| # | Task | Deps | Priority | Effort | Group |
|---|------|------|----------|--------|-------|
| 1 | uv project + `backend/pyproject.toml` | — | Crítica | M | WU-1 |
| 2 | Folder + package tree (21 seams + main.py) | 1 | Crítica | M | WU-1 |
| 11 | ruff config + pre-commit hooks | 1 | Alta | S | WU-1 |
| 3 | Config — pydantic-settings `Settings` | 1 | Crítica | M | WU-2 |
| 4 | Logging bootstrap `core/logging.py` | 3 | Alta | S | WU-2 |
| 5 | DB bootstrap `core/db.py` + `repositories/base.py` | 3 | Alta | M | WU-2 |
| 6 | Envelope schemas | 1 | Alta | S | WU-2 |
| 7 | api/v1 router (health + version) | 3, 6 | Crítica | M | WU-2 |
| 8 | `main.py` app factory | 3, 4, 5, 7 | Crítica | M | WU-3 |
| 9 | Scripts (`run_backend.sh`, `init_db.sh`) | 8 | Alta | S | WU-3 |
| 10 | Hygiene (`.gitignore` + `.env.example`) | 1 | Media | S | WU-3 |
| 12 | Tests (smoke + config) | 7, 8 | Crítica | M | WU-3 |
| 13 | README documentation | 8 | Media | S | WU-3 |

## Task 1 — uv project + `backend/pyproject.toml`
**Priority**: Crítica · **Effort**: M · **Group**: WU-1
- [x] `uv init backend` (src-layout; package root `backend`, import path `backend.app`).
- [x] Add deps `fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy pytest httpx ruff pre-commit`; commit `uv.lock` (REQ-08 reproducibility).
- [x] `[tool.pytest.ini_options] testpaths=["tests"] pythonpath=["."]` in `backend/pyproject.toml`.
**Acceptance**: `uv run pytest` discovers tests; `backend` installable; deps pinned; Python `>=3.12`, pydantic v2.

## Task 2 — Folder + package tree seams (REQ-01)
**Deps**: Task 1 · **Priority**: Crítica · **Effort**: S · **Group**: WU-1
- [x] Create `backend/app/<pkg>/__init__.py` responsibility docstring for all 21 seams (design §Package Seams).
- [x] `backend/app/analytics/__init__.py` docstring asserts composition over `statistics`+`probability` (confirmed).
- [x] `__init__.py` only — no logic, tables, routes.
**Acceptance**: exactly 21 seam packages + `main.py` module = 22 distinct units; exact §4 names; no invented `domain/`; ruff clean over tree.

## Task 3 — Centralized config `backend/app/config/settings.py` (REQ-03)
**Deps**: Task 1 · **Priority**: Crítica · **Effort**: M · **Group**: WU-2
- [x] pydantic-settings v2 `Settings`, `SettingsConfigDict(env_prefix="LIP_", env_file=".env")`; sections app/api/database/logging/paths.
- [x] Lazy cached singleton `get_settings()`; secrets from env only; single access path.
**Acceptance**: defaults→env precedence deterministic; `LIP_APP_NAME` override respected; no distinct access paths.

## Task 4 — Logging bootstrap `backend/app/core/logging.py` (REQ-04)
**Deps**: Task 3 · **Priority**: Alta · **Effort**: S · **Group**: WU-2
- [x] `configure_logging(level)` stdlib-only; format `%(asctime)s|%(levelname)s|%(name)s|%(message)s`; loggers `logging.getLogger("backend.app.<module>")`.
**Acceptance**: level driven by `settings.logging.level`; startup line in format; names track package paths.

## Task 5 — DB bootstrap `core/db.py` + `repositories/base.py` (REQ-05)
**Deps**: Task 3 · **Priority**: Alta · **Effort**: M · **Group**: WU-2
- [x] `create_engine(settings.database.url)`; `init_db()` creates empty SQLite file (`database/lip.db`) — **no** `create_all`.
- [x] `repositories/base.py`: declarative `Base` + session factory; dialect from config `url` (engine/session built from settings).
**Acceptance**: empty file, 0 tables; no SQLite-only code outside `repositories/`.

## Task 6 — Envelope schemas (REQ-02)
**Deps**: Task 1 · **Priority**: Alta · **Effort**: S · **Group**: WU-2
- [x] Pydantic v2 schemas `{success, data|error, timestamp}`; timestamp ISO 8601 UTC.
**Acceptance**: envelope shape reusable by all endpoints.

## Task 7 — `api/v1` router (health + version) (REQ-02)
**Deps**: Tasks 3, 6 · **Priority**: Crítica · **Effort**: M · **Group**: WU-2
- [x] `api/v1/router.py`: `GET /health` → `{success,data:{status:"ok"},timestamp}`; `GET /version` → `{success,data:{version,app},timestamp}`.
- [x] Export `api_v1_router` to mount under `/api/v1`.
**Acceptance**: health 200 envelope; version present (smoke).

## Task 8 — App factory `main.create_app()` (REQ-02)
**Deps**: Tasks 3, 4, 5, 7 · **Priority**: Crítica · **Effort**: M · **Group**: WU-3
- [x] `create_app()`: bootstrap logging, build Engine, CORS (Vite dev `http://localhost:5173`), mount `api_v1_router` under `/api/v1`, global handler mapping HTTPException/validation/unhandled → envelope, lifespan startup logs.
- [x] FastAPI version compatible with pydantic v2.
**Acceptance**: boots via `uvicorn backend.app.main:create_app`; error paths → envelope.

## Task 9 — Dev scripts (REQ-07)
**Deps**: Task 8 · **Priority**: Alta · **Effort**: S · **Group**: WU-3
- [x] `scripts/run_backend.sh` → `uv run uvicorn backend.app.main:create_app --reload`.
- [x] `scripts/init_db.sh` → create DB path + empty `database/lip.db`.
**Acceptance**: both run; executable bit set; init_db creates empty DB.

## Task 10 — Hygiene `.gitignore` + `.env.example` (REQ-07)
**Deps**: Task 1 · **Priority**: Media · **Effort**: S · **Group**: WU-3
- [x] Repo-root `.gitignore`: `__pycache__/`, `.venv/`, `.env`, `*.db*`, `.ruff_cache/`, `.pytest_cache/`, `/database/` (repo-root DB dir per design §layout + implementation).
- [x] `config/.env.example` placeholders only, **no secrets**.
**Acceptance**: ignored artifacts untracked; `.env.example` zero real values.

## Task 11 — ruff + pre-commit (REQ-06)
**Deps**: Task 1 · **Priority**: Alta · **Effort**: S · **Group**: WU-1
- [x] `[tool.ruff]` line-length=100, lint `["E","F","I","UP","B"]`, format default.
- [x] `.pre-commit-config.yaml` hooks: ruff (check) + ruff-format.
**Acceptance**: `uv run ruff check .` + `ruff format --check .` pass; `pre-commit run --all-files` green.

## Task 12 — Tests: smoke + config (REQ-02/03/06)
**Deps**: Tasks 1, 8 · **Priority**: Crítica · **Effort**: M · **Group**: WU-3
- [x] `backend/tests/test_smoke.py`: TestClient; `/api/v1/health` → 200 `success:true` envelope; `/version`.
- [x] `backend/tests/test_config.py`: `LIP_APP_NAME` override applies; unset→default.
**Acceptance**: `uv run pytest` green (uses `pythonpath=["."]`).

## Task 13 — README (REQ-07/08)
**Deps**: Tasks 1, 8 · **Priority**: Media · **Effort**: S · **Group**: WU-3
- [x] Document layout, engine seams, .config precedence, scripts, boundary (frontend chained slice / Fase-1 schema out of scope).
**Acceptance**: README reflects structure + conventions; boundary explicit.

## Dependency Graph
```
Task 1 ─► 2, 3, 6, 11 (parallel after init)
Task 3 ─► 4, 5, 7
Task 6 ─► 7
Task 7 ─► 8
Tasks 3,4,5,7 ► 8
Task 8 ─► 9
Task 1 ─► 10, 12, 13
Task 8 ─► 12
```

## Parallel sets
- **P1 (after Task 1)**: 2 (tree) ∥ 3 (config) ∥ 6 (envelope) ∥ 11 (ruff).
- **P2 (after Task 3)**: 4 (logging) ∥ 5 (db) ∥ 7 (router).
- **P3 (after Task 8)**: 9 (scripts) ∥ 12 (tests) ∥ 13 (README).

## Frozen boundary for this change
No engine algorithm, no schema/migration (`Base.metadata.create_all` deferred to Fase 1), no frontend, no `domain/` tree. `main.py` is a module; `analytics` composes `statistics`+`probability`. `models/`, `services/` exist as empty seams only.