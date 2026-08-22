# Design: Fase 18 — Documentación

## Technical Approach

Reconcile all docs with verified reality, driven by ONE baseline table (DOC-009 anchor). API reference uses **hybrid** source of truth: curated prose + marker-block generated reference + path-parity contract test (anti-drift). S0 fixes the 26 pre-existing ruff errors to unblock `verify.build_command`. All numbers re-probed 2026-08-20: OpenAPI 49 paths/53 ops, alembic 0001–0016, ruff 26 errors, 12 engine dirs, 12 frontend routes + 404.

> Ruff live split (spec drift): 26 errors = **6 src in 5 files + 20 tests in 11 files**; 17 auto-fixable (I001×6, F401×11), 9 manual (E501×7, B007×1, F841×1).

## Architecture Decisions

| Decision | Options (tradeoff) | Decision |
|---|---|---|
| API truth source | generated-only (accurate, no prose) vs manual (re-drifts) | **Hybrid**: curated guide + generated reference spliced between markers |
| Generator location | `scripts/` (shell-y) vs `backend/scripts/` vs `docs/api/` (artifact colocated; outside `ruff check .` cwd=`backend/`) | **`docs/api/generate_reference.py`** (new `docs/` tree) |
| Extraction mechanism | live server + `/openapi.json` (ops cost, fragile) vs import factory (conftest precedent, no DB touch) | **Import `backend.app.main:create_app` → `app.openapi()`** |
| Contract test scope | docs⊆OpenAPI (misses missing docs) vs equal sets | **Both directions**, diff-listing on failure |
| Ruff fix | one PR (mechanical, safe) | **One S0 PR** (26 fixes, 16 files) |

## Doc Baseline (single source of truth — DOC-009)

| Slice / Target | Source-of-truth inputs (verified) | Outline (sections) | Acceptance |
|---|---|---|---|
| S0: 5 src files (`api/v1/meta.py`, `cli.py`, `meta/normalization.py`, `meta/types.py`, `schemas/meta.py`) + 11 test files | `ruff check .` (26 errors listed above) | — (lint-only) | `ruff check .` exit 0; no behavior change |
| S1: `API_SPECIFICATION.md` (rewrite), `docs/api/generate_reference.py` (new), `backend/tests/api/test_docs_contract.py` (new) | `create_app().openapi()` (49/53); `api/v1/router.py` 14 routers: lotteries, draws, statistics, feature_engine, probability, graph, ml, opt, bt, exp, meta, gen, assistant + health/version | 1. Principios/convenciones (base URL `/api/v1`, envelope `SuccessEnvelope`, `api/errors.py` codes, auth: none v1) · 2. Referencia por path (generated markers) | contract test green: documented == OpenAPI paths; `/ml/predict`, `/dl/*`, `/statistics/summary` etc. absent |
| S2: `SYSTEM_ARCHITECTURE.md` (rewrite, 511→current) | 28 module dirs `backend/src/backend/app/`; `main.py:create_app`; `router.py`; alembic `versions/0001..0016` head `0016_exp_comparisons_run_ids`; `config/settings.py`; frontend `App.tsx` | 1. Visión general · 2. Mapa de módulos (28) · 3. Capas y seams de engines · 4. Ciclo de vida de snapshots · 5. DB/migraciones · 6. CLI `lip` · 7. Frontend (12 rutas) · 8. Despliegue | grep "Draft" → 0; claims trace to source |
| S3: `MANUAL_TECNICO.md` (new) | 12 engines (`statistics probability feature_engineering graph ml dl opt backtesting experiments meta generators ai`); `cli.py` 12 grupos: `import dataset-generate statistics feature-engine probability graph ml opt exp bt meta gen`; `settings.py` LIP_*: `app_name app_version debug api_v1_prefix allowed_origins database_url database_path logging_level database_dir stats_retention_generations`; alembic; `api/errors.py` | 1. Intro · 2–13. 12 engines · 14. CLI `lip` · 15. Config `LIP_*` · 16. DB/migraciones · 17. Observabilidad/errores | each engine/command/var traced to module; none invented |
| S4: `MANUAL_USUARIO.md` (new) | `App.tsx` routes: `/`, `historial`, `estadisticas`, `heatmaps`, `tendencias`, `redes`, `monte-carlo`, `ia`, `modelos`, `experimentos`, `backtesting`, `generador`, `*`(404) | 1. Intro · 2. Instalación rápida · 3–14. Rutas + 404 · 15. CLI avanzado | every route has section; no invented page |
| S5: `INSTALL.md`, `backend/README.md`, `frontend/README.md` (new) | `pyproject.toml` (`lip = "backend.app.cli:main"`, uv), `alembic.ini`, `scripts/init_db.sh`, `scripts/run_backend.sh`, `package.json` (dev/build/lint/test), `vite.config.ts` | 1. Requisitos · 2. Backend (uv+venv+alembic head) · 3. Frontend (npm) · 4. DB init · 5. CI | commands byte-verbatim from manifests; fresh install reproduces |
| S6: `CONTRIBUTING.md` (new) | `AGENTS.md`; git log (conventional commits, "F17 PR x/y — … (#n)" chain pattern); `openspec/config.yaml` (`build_command: ruff check .`, `test_command: backend/.venv/bin/pytest`); review budget 400 | 1. Workflow SDD · 2. Commits/PRs · 3. Gates ruff+pytest · 4. Review budget · 5. LICENSE/CHANGELOG (decision point) | conventions match history; license absence documented |
| S7: `DATABASE_SCHEMA.md`, `PROJECT_STATUS.md`, `ENGINE_SPECIFICATIONS.md` (modify) | alembic 0001–0016 (tables `exp_* bt_* ml_* opt_* graph_*`); git log F12–F17; real DL (no router mounted) / gen (`/gen/*` live) | 1. Migraciones 0001–0016 · 2. Tablas · 3. F12–F17 · 4. §10 DL + generators corregidos · 5. Deuda aceptada (DOC-010) | migrations 0001–0016 referenced; F12–F17 recorded; §10 corrected |

## S1: Generator + Contract Test (concrete)

**`docs/api/generate_reference.py`** (~130 lines): `sys.path.insert(0, <repo>/backend)` (precedent: `alembic/env.py` E402/I001 per-file-ignore); `from backend.app.main import create_app`; `schema = create_app().openapi()` (no DB hit); for each sorted path+method emit `### {METHOD} {path}` + summary, tags, params (name/in/required/type), body content type, 200 schema name; wrap in `<!-- GENERATED-API-REFERENCE:START -->`/`END`; regex-splice the block into `API_SPECIFICATION.md` (byte-stable → idempotent: re-run diffs empty). Run manually from repo root: `backend/.venv/bin/python docs/api/generate_reference.py`. **Not in CI** (F17 CI untouched).

**`backend/tests/api/test_docs_contract.py`** (~90 lines): module-scoped fixture `openapi = create_app().openapi()`; parse markers from `API_SPECIFICATION.md` (`Path(__file__).resolve().parents[3]`); assert `documented == openapi_paths` both directions, listing diffs (covers "new router detected" scenario: fail + list undocumented path). Follows `tests/api/` style (conftest `client` pattern), ruff-clean, fast, no DB, no coverage config touched (report-only suite).

## S0: Ruff Mechanics

1. `cd backend && .venv/bin/ruff check . --fix` → auto-fixes 17 (I001×6, F401×11).
2. Manual 9: wrap E501×7 (`cli.py:958`, `meta/types.py:48`, `tests/meta/test_meta_schemas.py:133`, `test_ranking.py:28`, `test_snapshot_store.py:39`, `test_types.py:1`, `test_migrations.py:696`); rename unused loop var (B007, `meta/normalization.py:54`); remove unused `single_val` (F841, `:68`).
3. No `ruff format`, no `--unsafe-fixes` (no churn beyond the 26). Gate: `ruff check .` exit 0.

## PR Split (auto-chain, stacked-to-main; generated golden lines excluded per §E)

| PR | Content | Authored est. |
|---|---|---|
| S0-1 | ruff fixes (16 files) | ~60 |
| S1-1 | generator + contract test + doc markers | ~230 |
| S1-2 | generated reference body (golden) | ~0 |
| S1-3 | curated prose (principios, envelope, errores) | ~200 |
| S2-1 | arch: visión, módulos, capas, seams | ~280 |
| S2-2 | arch: snapshots, DB, CLI, frontend, despliegue | ~270 |
| S3-1 | manual: stats/prob/fe/graph | ~300 |
| S3-2 | manual: ml/dl/opt/bt/exp | ~300 |
| S3-3 | manual: meta/gen/ai + CLI + config + DB + obs | ~300 |
| S4-1 | user manual: intro + 6 páginas | ~320 |
| S4-2 | user manual: 6 páginas + 404 + CLI | ~330 |
| S5-1 | INSTALL + 2 READMEs | ~350 |
| S6-1 | CONTRIBUTING | ~300 |
| S7-1 | 3 aux docs sync | ~350 |

## Verification Strategy

| Gate | Mechanism |
|---|---|
| S0 | `ruff check .` exit 0; `pytest tests/meta tests/probability tests/test_migrations.py` — no new failures |
| S1 | `pytest tests/api/test_docs_contract.py`; grep F18 docs for `/ml/predict`, `/dl/` → 0 |
| S2–S7 | grep "Draft"/fase-refs = 0; `lip --help` + `lip <cmd> --help` (no DB) vs doc; route table from `App.tsx` vs manual; commands byte-compare vs manifests; grep migrations 0001–0016, F12–F17; claims traced via CodeGraph |
| Final | `ruff check .` + full pytest (5 optuna failures recorded as DOC-010) + contract test green |

"No invented content" = every endpoint/module/command/config-var claim resolves to a symbol verified above; baseline table is the audit checklist.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary: S0 is lint hygiene; generator/test are plain python (manual invoke / pytest); zero runtime code changes.

## Migration / Rollout

No migration. Rollback: per-PR `git revert` — docs-only commits, zero runtime impact (S0 revert restores 26 lint errors, no behavior delta).

## Open Questions

None blocking. S6 keeps the LICENSE/CHANGELOG decision point (documented absence acceptable per DOC-006).