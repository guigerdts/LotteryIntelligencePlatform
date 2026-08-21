# Tasks: Fase 18 — Documentación

Store: hybrid · Date: 2026-08-20 · Deliverables Spanish; SDD artifacts English.
Canonical apply order: **S0-1 → S1-1 → S1-2 → S1-3 → S2-1 → S2-2 → S3-1 → S3-2 → S3-3 → S4-1 → S4-2 → S5-1 → S6-1 → S7-1** (14 stacked-to-main PRs, conventional commits `[T-Sx-yy]`, no AI attribution). Planning only — no implementation here. Facts re-probed 2026-08-20: OpenAPI 49/53, alembic 0001–0016, ruff 26, 12 engines, 12 rutas + 404.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines (authored) | ~3390 total (per-PR table below) |
| 400-line budget risk | Low per PR / High total |
| Chained PRs recommended | Yes |
| Suggested split | 14 PRs, one per slice: S0-1 → S1-1/2/3 → S2-1/2 → S3-1/2/3 → S4-1/2 → S5-1 → S6-1 → S7-1 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main (owner pre-authorized) |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

**Split-on-overage rule:** if any PR's authored `git diff --numstat` exceeds 400 additions+deletions at apply (generated golden block in S1-2 excluded), split that slice into further chained PRs. NO `size:exception`.

### Suggested Work Units

| PR | Goal | Focused test command | Runtime harness | Rollback boundary |
|----|------|----------------------|-----------------|-------------------|
| S0-1 | ruff 26 fixes | `cd backend && .venv/bin/ruff check .` exit 0 | `pytest tests/meta tests/probability tests/test_migrations.py -q` | revert S0 commit (restores 26 errors, no behavior delta) |
| S1-1 | generator + contract test + markers | `backend/.venv/bin/pytest backend/tests/api/test_docs_contract.py -q` | run `backend/.venv/bin/python docs/api/generate_reference.py` | delete `docs/api/` + contract test + revert markers |
| S1-2 | generated reference body (golden) | re-run generator → `git diff` empty on block | generator idempotency run | revert generated block only |
| S1-3 | curated prose (principios, envelope, errores) | contract test green; grep `/ml/predict`,`/dl/` → 0 | `create_app().openapi()` diff-listing | revert prose sections in API_SPECIFICATION.md |
| S2-1 | arch §1–3 (visión, módulos, seams) | `grep -in "draft" SYSTEM_ARCHITECTURE.md` → 0 | `backend/.venv/bin/lip --help` (no DB) | revert SYSTEM_ARCHITECTURE.md rewrite |
| S2-2 | arch §4–8 (snapshots, DB, CLI, frontend, despliegue) | grep Draft/fase-refs → 0; `backend/.venv/bin/alembic heads` = 0016 | route table vs `App.tsx` | revert SYSTEM_ARCHITECTURE.md sections |
| S3-1 | manual: stats/prob/fe/graph | `backend/.venv/bin/lip --help` vs doc | `lip <cmd> --help` per documented group | delete MANUAL_TECNICO.md |
| S3-2 | manual: ml/dl/opt/bt/exp | `lip <cmd> --help` vs doc; DL = no router mounted | no-DB CLI probe | delete MANUAL_TECNICO.md |
| S3-3 | manual: meta/gen/ai + CLI + config + DB + obs | every `LIP_*` var traced to `config/settings.py` | `backend/.venv/bin/lip --help` (12 grupos) | delete MANUAL_TECNICO.md |
| S4-1 | user manual intro + 6 páginas | route parity vs `App.tsx` (every route has section) | `backend/.venv/bin/lip --help` for CLI section | delete MANUAL_USUARIO.md |
| S4-2 | user manual 6 páginas + 404 + CLI | no invented page; CLI examples runnable | `lip <cmd> --help` output match | delete MANUAL_USUARIO.md |
| S5-1 | INSTALL + 2 READMEs | commands byte-compare vs manifests | `backend/.venv/bin/python -c "import backend.app.main"` + `npm run build` | delete INSTALL.md + 2 READMEs |
| S6-1 | CONTRIBUTING | conventions match `git log` + AGENTS.md | `git log --oneline -20` audit | delete CONTRIBUTING.md |
| S7-1 | 3 aux docs + DOC-009/010 | grep migrations 0001–0016, F12–F17 → present | `backend/.venv/bin/alembic heads` = 0016 | revert 3 aux docs |

## Task Table (grouped per PR)

### PR S0-1 — Ruff P0 (DOC-008) [~60 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S0-01 | S0-1 | Fix 6 src ruff errors: I001×2 (`api/v1/meta.py:7`, `schemas/meta.py:7`), E501×2 (`cli.py:958`, `meta/types.py:48` — wrap), B007 (`meta/normalization.py:54` rename unused loop var), F841 (`:68` remove `single_val`). No `ruff format`, no `--unsafe-fixes`. | `cd backend && .venv/bin/ruff check .` reports 0 src errors | `backend/src/backend/app/api/v1/meta.py`, `schemas/meta.py`, `cli.py`, `meta/types.py`, `meta/normalization.py` |
| T-S0-02 | S0-1 | Fix 20 test-file ruff errors: run `.venv/bin/ruff check . --fix` (auto-fixes 17: I001×6, F401×11), then manual E501×5 wraps (`tests/meta/test_meta_schemas.py:133`, `test_types.py:1`, `test_ranking.py:28`, `test_snapshot_store.py:39`, `tests/test_migrations.py:696`). | `ruff check .` reports 0 test errors | `backend/tests/meta/{test_meta_schemas,test_types,test_ranking,test_snapshot_store,test_selection,test_meta_errors,test_context}.py`, `tests/probability/{test_probability_service,test_e2e,test_snapshot_store}.py`, `tests/test_migrations.py` |
| T-S0-03 | S0-1 | Gate: `ruff check .` exit 0 (16 files); `pytest tests/meta tests/probability tests/test_migrations.py -q` → no new failures (5 optuna failures excluded, DOC-010). | gate green, zero behavior change | — (verification only) |

### PR S1-1 — Generator + contract test + markers (DOC-001) [~230 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S1-01 | S1-1 | Create `docs/api/generate_reference.py` (~130 ln): `sys.path.insert(0, <repo>/backend)`; `from backend.app.main import create_app`; `schema = create_app().openapi()` (no DB hit); per sorted path+method emit `### {METHOD} {path}` + summary, tags, params (name/in/required/type), body content-type, 200 schema name; wrap in `<!-- GENERATED-API-REFERENCE:START/END -->`; regex-splice into `API_SPECIFICATION.md` (byte-stable, idempotent). Manual run: `backend/.venv/bin/python docs/api/generate_reference.py`. NOT in CI. | script runs, splices block, re-run → no diff; ruff-clean | create `docs/api/generate_reference.py` |
| T-S1-02 | S1-1 | Create `backend/tests/api/test_docs_contract.py` (~90 ln): module-scoped fixture `openapi = create_app().openapi()`; parse marker block from `API_SPECIFICATION.md` (`Path(__file__).resolve().parents[3]`); assert `documented == openapi_paths` BOTH directions, listing diffs (covers DOC-001 "new router detected"). Follows `tests/api/` conftest style; no DB. | `backend/.venv/bin/pytest backend/tests/api/test_docs_contract.py -q` green | create `backend/tests/api/test_docs_contract.py` |
| T-S1-03 | S1-1 | Replace stale path reference in `API_SPECIFICATION.md` with the START/END marker block; run generator once to splice the generated body. | markers present; block covers 49 paths/53 ops | modify `API_SPECIFICATION.md` |

### PR S1-2 — Generated reference body (golden) [~0 authored ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S1-04 | S1-2 | Commit the generated reference block (golden — excluded from authored count). Re-run generator → `git diff` empty on the block; every documented path traces to `create_app().openapi()` (no invented content). | idempotent re-run; 49/53 paths in doc | `API_SPECIFICATION.md` (generated block only) |

### PR S1-3 — Curated prose (DOC-001) [~200 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S1-05 | S1-3 | Write curated intro (Spanish): principios/convenciones — base URL `/api/v1`, envelope `SuccessEnvelope`, error codes from `api/errors.py`, auth: none in v1; 14 routers listed (lotteries, draws, statistics, feature_engine, probability, graph, ml, opt, bt, exp, meta, gen, assistant + health/version). Every claim traced to `api/v1/router.py` + `api/errors.py`. | no invented endpoint; prose consistent with generated block | modify `API_SPECIFICATION.md` (prose sections) |
| T-S1-06 | S1-3 | Gate: contract test green; `grep -rn "/ml/predict\|/dl/" API_SPECIFICATION.md` → 0; curated + generated paths union == 49/53. | all gates pass | — (verification only) |

### PR S2-1 — Architecture §1–3 (DOC-002) [~280 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S2-01 | S2-1 | Rewrite `SYSTEM_ARCHITECTURE.md` §1–3 (Draft→current, Spanish): visión general, mapa de módulos (28 dirs `backend/src/backend/app/`), capas y seams de engines. Sources: module dirs, `main.py:create_app`, `api/v1/router.py`. Trace every module claim via CodeGraph. | §1–3 grep "Draft" → 0; module count 28 matches `ls` | modify `SYSTEM_ARCHITECTURE.md` |
| T-S2-02 | S2-1 | Gate: `grep -in "draft" SYSTEM_ARCHITECTURE.md` → 0; no pre-implementation fase references in §1–3. | gate green | — (verification only) |

### PR S2-2 — Architecture §4–8 (DOC-002) [~270 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S2-03 | S2-2 | Rewrite §4–8 (Spanish): ciclo de vida de snapshots; DB/migraciones (alembic 0001–0016, head `0016_exp_comparisons_run_ids`); CLI `lip`; frontend (12 rutas + 404 from `App.tsx`); despliegue (`scripts/`). Sources: `alembic/versions/`, `cli.py`, `App.tsx`, `scripts/*`. | every claim resolves to source | modify `SYSTEM_ARCHITECTURE.md` |
| T-S2-04 | S2-2 | Gate: whole-doc grep Draft/fase-refs → 0; `backend/.venv/bin/alembic heads` = 0016; route list matches `App.tsx`; claims traced via CodeGraph. | all gates pass | — (verification only) |

### PR S3-1 — Manual técnico: stats/prob/fe/graph (DOC-003) [~300 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S3-01 | S3-1 | Create `MANUAL_TECNICO.md` (Spanish): intro + sections for engines statistics, probability, feature_engineering, graph — each grounded in its module dir. No invented APIs/commands. | 4 engine sections trace to modules | create `MANUAL_TECNICO.md` |
| T-S3-02 | S3-1 | Gate: each engine claim resolves to module symbol (CodeGraph); commands match `cli.py` groups. | no invented content | — (verification only) |

### PR S3-2 — Manual técnico: ml/dl/opt/bt/exp (DOC-003) [~300 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S3-03 | S3-2 | Add sections (Spanish): ml, dl (document REAL state — no router mounted), opt, backtesting, experiments. Sources: module dirs + `api/v1` routers. | DL section states no mounted router; claims traced | modify `MANUAL_TECNICO.md` |

### PR S3-3 — Manual técnico: meta/gen/ai + CLI + config + DB + obs (DOC-003) [~300 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S3-04 | S3-3 | Add sections (Spanish): meta, generators, ai; CLI `lip` (12 grupos: import dataset-generate statistics feature-engine probability graph ml opt exp bt meta gen); config `LIP_*` (settings.py: app_name app_version debug api_v1_prefix allowed_origins database_url database_path logging_level database_dir stats_retention_generations); DB/migraciones (0001–0016); observabilidad (`api/errors.py`). | every var/command traced to `settings.py`/`cli.py` | modify `MANUAL_TECNICO.md` |
| T-S3-05 | S3-3 | Gate: `backend/.venv/bin/lip --help` + `lip <cmd> --help` (no DB) match doc; all 12 engines covered; zero invented config vars. | all gates pass | — (verification only) |

### PR S4-1 — Manual de usuario: intro + 6 páginas (DOC-004) [~320 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S4-01 | S4-1 | Create `MANUAL_USUARIO.md` (Spanish): intro, instalación rápida, pages `/` Home, `/historial`, `/estadisticas`, `/heatmaps`, `/tendencias`, `/redes` — matching real components. Source: `App.tsx` routes. | 6 pages + intro match real routes | create `MANUAL_USUARIO.md` |

### PR S4-2 — Manual de usuario: 6 páginas + 404 + CLI (DOC-004) [~330 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S4-02 | S4-2 | Add pages (Spanish): `/monte-carlo`, `/ia`, `/modelos`, `/experimentos`, `/backtesting`, `/generador` + `*` (404) + CLI avanzado with runnable examples. | all 13 `App.tsx` entries have sections; no invented page | modify `MANUAL_USUARIO.md` |
| T-S4-03 | S4-2 | Gate: route parity vs `App.tsx` (13 entries); CLI examples produce described output (`lip <cmd> --help`); no invented page. | all gates pass | — (verification only) |

### PR S5-1 — Install + READMEs (DOC-005) [~350 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S5-01 | S5-1 | Create `INSTALL.md` (Spanish): requisitos; backend uv/venv + `alembic upgrade head` (→ 0016); frontend npm (dev/build/lint/test); DB init (`scripts/init_db.sh`); CI. Commands byte-verbatim from `pyproject.toml`, `package.json`, `alembic.ini`, `vite.config.ts`. | every command appears verbatim in a manifest | create `INSTALL.md` |
| T-S5-02 | S5-1 | Create `backend/README.md` + `frontend/README.md` (Spanish): per-tree quickstart + test/lint commands from manifests. | commands byte-match manifests | create `backend/README.md`, `frontend/README.md` |
| T-S5-03 | S5-1 | Gate: byte-compare all documented commands vs manifests; `backend/.venv/bin/python -c "import backend.app.main"` + `npm run build` green. | all gates pass | — (verification only) |

### PR S6-1 — Contributing (DOC-006) [~300 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S6-01 | S6-1 | Create `CONTRIBUTING.md` (Spanish): workflow SDD (openspec), commits/PRs (conventional, no AI attribution, F17 chain pattern), gates (ruff + pytest), 400-line review budget, LICENSE/CHANGELOG decision point — document absence, do NOT invent a license. Sources: `AGENTS.md`, `git log`, `openspec/config.yaml`. | conventions match history; license absence documented | create `CONTRIBUTING.md` |
| T-S6-02 | S6-1 | Gate: `git log --oneline -20` + AGENTS.md audit → documented conventions match practice; LICENSE absence stated as decision point (non-blocking). | all gates pass | — (verification only) |

### PR S7-1 — Aux docs sync + DOC-009/010 (DOC-007/009/010) [~350 ln]

| ID | Slice/PR | Description | Acceptance | Files |
|----|----------|-------------|------------|-------|
| T-S7-01 | S7-1 | Sync `DATABASE_SCHEMA.md`: reference migrations 0001–0016 and tables `exp_*`/`bt_*`/`ml_*`/`opt_*`/`graph_*`. Source: `alembic/versions/` + models. | every migration referenced consistently | modify `DATABASE_SCHEMA.md` |
| T-S7-02 | S7-1 | Sync `PROJECT_STATUS.md`: record F12–F17 from `git log`; remove stale closure date (2026-08-10). | F12–F17 recorded, no stale date | modify `PROJECT_STATUS.md` |
| T-S7-03 | S7-1 | Correct `ENGINE_SPECIFICATIONS.md` §10: DL (no router mounted — real state) + generators (`/gen/*` live); add deuda aceptada subsection. | §10 matches real DL/gen state | modify `ENGINE_SPECIFICATIONS.md` |
| T-S7-04 | S7-1 | Gate: grep migrations 0001–0016 + F12–F17 present; `backend/.venv/bin/alembic heads` = 0016; §10 corrected. | all gates pass | — (verification only) |
| T-DOC-009 | S7-1 | Cross-doc consistency audit (DOC-009): all F18 docs share one baseline (49/53 API, 16 migrations, 12 engines, 13 rutas, ruff clean); same facts/numbers across docs; zero invented endpoints/modules/commands/config. | baseline table = audit checklist, all docs consistent | — (verification only) |
| T-DOC-010 | S7-1 | Register out-of-scope debt (DOC-010) in `PROJECT_STATUS.md` deuda aceptada + change debt notes: 5 `tests/opt` failures (optuna absent; uv.lock stale), perf baselines (owner: never touch), F17 coverage/CI untouched; cite measured values as-is (backend 91.88%, frontend 95.22%). | debt appears with owner decisions; baselines untouched | modify `PROJECT_STATUS.md` + change debt notes |

## Verification / Gates Strategy (final)

- Final gate: `cd backend && .venv/bin/ruff check .` exit 0 + `backend/.venv/bin/pytest backend/tests/api/test_docs_contract.py -q` + full pytest per-directory (5 optuna failures recorded as DOC-010, never hidden).
- Per-PR `git diff --numstat` ≤400 authored (generated S1-2 block excluded); overage → further split, no `size:exception`.
- "No invented content" = every endpoint/module/command/config-var claim resolves to a symbol verified above; baseline table is the audit checklist.

## Progress (machine-readable checkboxes)

- [x] T-S0-01 ruff src fixes (5 files, 6 errors)
- [x] T-S0-02 ruff test fixes (11 files, 20 errors, 17 auto-fixable)
- [x] T-S0-03 gate: ruff check . exit 0 + pytest meta/probability/migrations no new failures
- [x] T-S1-01 docs/api/generate_reference.py (marker-block OpenAPI generator, idempotent)
- [x] T-S1-02 tests/api/test_docs_contract.py (path parity, both directions)
- [x] T-S1-03 API_SPECIFICATION.md markers + first splice
- [x] T-S1-04 generated reference body committed (golden, 49/53)
- [x] T-S1-05 curated prose: principios/envelope/errores/auth
- [x] T-S1-06 S1 gate: contract green, /ml/predict + /dl/ absent
- [x] T-S2-01 arch §1–3: visión, 25 módulos, capas/seams
- [x] T-S2-02 S2-1 gate: Draft → 0
- [x] T-S2-03 arch §4–8: snapshots, DB 0001–0016, CLI, frontend, despliegue
- [x] T-S2-04 S2-2 gate: Draft/fase-refs → 0, alembic head 0016
- [x] T-S3-01 manual: statistics/probability/feature_engineering/graph
- [ ] T-S3-02 S3-1 gate: engine claims traced
- [ ] T-S3-03 manual: ml/dl (no router)/opt/bt/exp
- [ ] T-S3-04 manual: meta/gen/ai + CLI 12 grupos + LIP_* + DB + obs
- [ ] T-S3-05 S3 gate: lip --help matches, 12 engines covered
- [ ] T-S4-01 manual usuario: intro + 6 páginas
- [ ] T-S4-02 manual usuario: 6 páginas + 404 + CLI avanzado
- [ ] T-S4-03 S4 gate: 13 rutas parity, CLI examples runnable
- [ ] T-S5-01 INSTALL.md (commands byte-verbatim)
- [ ] T-S5-02 backend/README.md + frontend/README.md
- [ ] T-S5-03 S5 gate: byte-compare vs manifests, npm run build
- [ ] T-S6-01 CONTRIBUTING.md (SDD, commits, gates, 400 budget, license point)
- [ ] T-S6-02 S6 gate: conventions match git log + AGENTS.md
- [ ] T-S7-01 DATABASE_SCHEMA.md sync (0001–0016)
- [ ] T-S7-02 PROJECT_STATUS.md sync (F12–F17)
- [ ] T-S7-03 ENGINE_SPECIFICATIONS.md §10 DL/gen corregido
- [ ] T-S7-04 S7 gate: migrations + F12–F17 referenced
- [ ] T-DOC-009 cross-doc consistency audit (single baseline)
- [ ] T-DOC-010 out-of-scope debt register (optuna/uv.lock/perf/CI)