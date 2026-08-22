# Exploration: Fase 18 — Documentación

- **Change (working key)**: `fase-18-documentation` (canonical name to finalize at proposal; mission working folder `fase-18`)
- **Store**: hybrid (engram + openspec)
- **Date**: 2026-08-20
- **Source**: IMPLEMENTATION_ROADMAP.md (Fase 18), live code inspection (CodeGraph + targeted runs), F17 archive (2026-08-20-fase-17-testing), coverage-history.json
- **Status**: READ-ONLY — no code or docs modified

---

## 1. What Fase 18 IS (roadmap definition)

From `IMPLEMENTATION_ROADMAP.md` (Versión 1.0):

> **Fase 18 — Documentación**
> Generar: API · Manual técnico · Manual de usuario · Arquitectura actualizada · Guías de instalación · Guías de contribución

DoD (roadmap-wide, applies to every fase): all tasks implemented; tests pass; **documentation updated**; no critical open errors; acceptance criteria met; reproducible and traceable.

Phase chain: ... → F16 Performance → F17 Testing → **F18 Documentation** → F19 Release Candidate. F17 is archived (cde0b81) and closed; F18 is the exact next phase.

### Interpretation (codebase reality)

| Roadmap deliverable | Current state | Gap |
|---|---|---|
| **API** | `API_SPECIFICATION.md` v1.0 (540 lines, 21 sections, ~40 documented paths) | **STALE / ASPIRATIONAL** — documents endpoints that do not exist (`/ml/predict`, `/ml/ranking`, `/dl/train|models|metrics` — no DL router mounted at all, `/statistics/summary|hot|cold|distribution|correlation`, `/probability/montecarlo|bayes|hypergeometric|binomial`, `/generator/run|history|{id}`, `/assistant/chat`, `/draws/latest`, `/experiments` vs real `/experiment/*`) and misses real endpoints (`/graph/*` ×3, `/meta/*` ×4, `/health`, `/version`, `/gen/*` ×4, `/opt/params`, `/feature-engine/*`, `/experiment/{id}/compare|export`). Real surface: **49 paths / 53 operations** in OpenAPI. |
| **Manual técnico** | None. `ENGINE_SPECIFICATIONS.md` (349 lines) is a spec, not a manual | CREATE |
| **Manual de usuario** | None. Frontend has 13 pages (Home, History, Statistics, Heatmaps, Trends, Networks, MonteCarlo, IA, Models, Experiments, Backtesting, Generator) + CLI (`lip import|dataset-generate|statistics|feature-engine|probability|graph|ml|opt|exp|bt|meta|gen`) | CREATE |
| **Arquitectura actualizada** | `SYSTEM_ARCHITECTURE.md` v1.0 **Draft**, pre-implementation (0 fase references). Real backend: 28 module dirs, 23,643 LOC, 14 mounted routers, alembic head `0016` | REWRITE |
| **Guías de instalación** | F0-era README only. No `INSTALL.md`, no frontend README, no backend README | CREATE/UPDATE |
| **Guías de contribución** | **None** — no CONTRIBUTING.md, no LICENSE, no CHANGELOG | CREATE |

Docs inventory today: 12 root `.md` files (4,548 lines): README (560), API_SPECIFICATION (540), SYSTEM_ARCHITECTURE (511), DATABASE_SCHEMA (497), IMPLEMENTATION_ROADMAP (456), CHARTER (355), SCIENTIFIC_METHODOLOGY (350), ENGINE_SPECIFICATIONS (349), FEATURE_ENGINEERING (307), LOTTERY_THEORY (500), PROJECT_STATUS (45, stale — closed 2026-08-10, missing F12–F17), sessionDIA-fase1 (67).

---

## 2. Current State (relevant to F18)

- **Backend**: `backend/src/backend/app/` — 28 modules (core, statistics, probability, feature_engineering, graph, ml, dl, opt, backtesting, experiments, meta, generators, ai, importers, api, services, repositories, schemas, models, config, utils, simulations, analytics, exporters, optimization, cli.py 49.8 KB). API: 14 routers mounted (`lotteries, draws, statistics, feature-engine, probability, graph, ml, opt, bt, exp, meta, gen, assistant` + health/version), 49 paths / 53 ops, envelope `SuccessEnvelope`, errors via `backend.app.api.errors`. CLI `lip` covers all engines. Alembic head `0016_exp_comparisons_run_ids`.
- **Frontend**: React + Vite + Tailwind; 13 pages, 15 components, 6 charts, 13 API services, 2 stores; 7,664 LOC (ts/tsx). No user-facing docs anywhere.
- **Testing (F17 output)**: backend 91.88% / frontend 95.22% coverage (report-only; hard gate `false` in coverage-history.json); CI `ci.yml` (sharded pytest + report-only coverage) + `performance.yml` (non-gate); Playwright E2E 1/1 core cycle; perf harness custom (N=5, exit 0, never fails workflow). Suite 1427 passed / 5 pre-existing failures in `tests/opt`.
- **Config**: `openspec/config.yaml` — verify `build_command: ruff check .`, `test_command: backend/.venv/bin/pytest`, coverage_threshold 0; context states "Spanish project documentation, English technical artifacts per SDD contract".

## 3. Real Objectives of Fase 18

1. **Reconcile the API reference with reality** — rewrite `API_SPECIFICATION.md` against the live OpenAPI schema (49 paths/53 ops); remove fictional endpoints, add missing ones; decide manual-vs-generated source of truth.
2. **Produce the technical manual** — engines, modules, layering, config (pydantic-settings, `LIP_*`), DB/migrations, CLI reference, observability.
3. **Produce the user manual** — page-by-page frontend guide (13 pages) + CLI usage for advanced users.
4. **Update the architecture document** — rewrite `SYSTEM_ARCHITECTURE.md` from Draft to current reality (28 modules, engine seams, snapshot lifecycle, deployment).
5. **Write installation guides** — backend (uv/venv, alembic, scripts), frontend (npm), DB init, CI workflow usage.
6. **Write contribution guides** — CONTRIBUTING.md (branch/PR/commit conventions, ruff/pytest, SDD workflow, review budget); resolve LICENSE/CHANGELOG question.
7. **Sync auxiliary docs** — DATABASE_SCHEMA.md (0 migration refs vs head 0016), PROJECT_STATUS.md (stale), ENGINE_SPECIFICATIONS.md accuracy pass.

## 4. Pending Debt (classified)

| Debt | Detail | Classification |
|---|---|---|
| 5 `tests/opt` failures | `test_bayesian.py` ×4 + `test_engine.py::test_all_implement_protocol` — `ModuleNotFoundError: No module named 'optuna'`. `optuna==4.0.0` IS in pyproject.toml (permitted runtime dep, OE-09; `test_opt_pr1.py` gates it out of F7/F8 trees) but NOT installed in the venv (uv.lock stale). Fix = env install; F16 explicitly out-of-scoped it ("installing deap/optuna — environment fix"), F17 kept it out | **related-deferrable** (env fix, not docs; do not absorb unless verify demands full green) |
| 26 ruff errors | `ruff check .` fails: 7 in src (`api/v1/meta.py` I001, `cli.py:958` E501, `meta/normalization.py` B007+F841, `meta/types.py` E501, `schemas/meta.py` I001), 19 in tests (`tests/meta/*` ×8, `tests/probability/*` ×10, `test_migrations.py` ×1). 17 auto-fixable. Breaks F17's `verify.build_command: ruff check .` | **related-deferrable** (code hygiene, not docs; recommend small P0 fix slice in proposal — cheap, unblocks verify) |
| Perf harness baselines | `config.yaml`: `cold_start` baseline 5.6 s vs measured 13–17 s (flagged FAIL, "real signal to review"); cached_statistics_get 0.045 s, parallel_bt_train 0.52 s mid-range estimates | **unrelated** — explicit owner decision: NON-BLOCKING, do not touch |
| uv.lock stale | Missing torch/deap/optuna (documented in F17 coverage-baseline; `uv sync` cannot resolve torch without PyTorch index) | **related-deferrable** |
| PROJECT_STATUS.md stale | Closed 2026-08-10, missing F12–F17 | **in-scope** (docs sync deliverable) |
| DATABASE_SCHEMA.md drift | 0 migration references; predates `exp_*`, `bt_*`, `ml_*`, `dl_*`, `opt_*`, `graph_*` tables | **in-scope** (part of "manual técnico"/"arquitectura actualizada") |
| ENGINE_SPECIFICATIONS.md accuracy | Section 10 (DL) has no API router today; generator section vs real `/gen/*` | **in-scope lite** (accuracy pass within technical manual work) |
| No LICENSE / CHANGELOG | Contribution guide conventionally references a license; none exists | **open question for owner** (create or reference?) |

## 5. Conflicts / Overlaps with F17

1. **Verify gate**: F17 set `verify.build_command: ruff check .` → today it fails on 26 pre-existing errors. F18 must either fix them (P0 slice) or explicitly scope them out with a recorded inconsistency (proposal rule).
2. **Full-suite verify**: F17's verify-report already records the 5 `tests/opt` failures as out-of-scope; F18 inherits the same situation (optuna env gap). Docs work adds no new backend code → no new failures expected, but full-suite runs (>15 min) remain the verify reality.
3. **Coverage**: F17's report-only → hard gate pending 3 consecutive qualifying runs (`coverage-history.json`, currently 3 runs recorded but `hard_gate: false`). F18 is docs: needs **no new coverage**, must not regress. CI sharding/report-only logic is untouched.
4. **CI workflows**: `ci.yml` + `performance.yml` built by F17. F18 doc-only changes don't affect CI. If F18 includes the ruff P0 fix, CI's `ruff check .`-equivalent expectations must be re-verified (currently `build_command` is only used by SDD verify, not CI — confirm).
5. **E2E**: F17's 1/1 Playwright core cycle can serve as reference flows for the user manual; no new E2E required by F18.
6. **Perf harness**: F17 ADR-6 custom harness; owner says non-blocking → F18 must NOT recalibrate baselines even though docs will reference performance characteristics.

## 6. Risks & Open Questions

1. **Scope explosion** — 6 deliverables + absorbing SYSTEM_ARCHITECTURE (511-line rewrite), DATABASE_SCHEMA, PROJECT_STATUS, plus new manuals = large. 400-line review budget per PR → each doc PR can exceed it alone (SYSTEM_ARCHITECTURE rewrite alone ≈ 500+ lines). Needs per-deliverable slices / chained PRs, or explicit owner acceptance of doc-size exception.
2. **Language** — roadmap deliverables named in Spanish; all existing project docs Spanish; SDD contract + config.yaml say "English technical artifacts". Established convention: project docs Spanish, SDD artifacts English. Needs explicit confirmation at proposal (recommend Spanish for deliverable docs, English for SDD artifacts).
3. **API truth source** — reconcile API_SPECIFICATION.md by hand (risk of re-drift) vs generate from OpenAPI/FastAPI `/docs` (accurate, less prose-friendly) vs hybrid (generated reference + curated guide) + optional CI contract test that documented paths == real paths. Decision belongs to design phase.
4. **optuna install** — installing it fixes 5 failures but reverses F16's explicit out-of-scope. Owner decision needed; do not silently absorb.
5. **LICENSE absence** — contribution guide needs a license story. Owner decision.
6. **Drift prevention** — without a CI check, docs will drift again (this is how API_SPEC got stale). Whether F18 includes a docs-accuracy CI check is a scope question.
7. **Frontend manual effort** — 13 pages + CLI, Medium-High effort; no prior user docs to build on.

## 7. Measurement Results (2026-08-20, cheap probes only — no full suite)

- API real surface: **49 paths / 53 operations** (OpenAPI via `create_app().openapi()`), 14 routers.
- API_SPECIFICATION.md documented paths: ~40; **~15+ do not exist**; **~15 real paths missing** (incl. all of `/graph/*`, `/meta/*`, `/gen/*`, `/health`, `/version`).
- Backend: 23,643 LOC (`src`), 28 module dirs, `cli.py` 49.8 KB (~1,300 lines), alembic head `0016`.
- Frontend: 7,664 LOC, 13 pages (+13 test files), 15 components, 6 charts, 13 services, 2 stores.
- tests/opt: **124 passed / 5 failed in 6.27 s** (optuna missing) — cheap to re-verify.
- ruff: **26 errors** (7 src / 19 tests), 17 auto-fixable — `ruff check .` fails today.
- Coverage (coverage-history.json): backend 91.88% (s3-fixed 2026-08-20), frontend 95.22%, `hard_gate: false`.
- Docs: 12 root `.md` (4,548 lines); no `docs/` dir; no CONTRIBUTING/LICENSE/CHANGELOG; no frontend/backend README; SYSTEM_ARCHITECTURE.md is Draft with 0 fase references; DATABASE_SCHEMA.md has 0 migration references.
- Perf harness (F17 config): cold_start baseline 5.6 s vs measured 13–17 s (FAIL flagged); cached_statistics_get 0.045 s; parallel_bt_train 0.52 s; tolerance 0.20; runs 5.
- CI: `ci.yml` (pytest shards + report-only coverage finalize), `performance.yml` (non-gate).

## 8. Approaches

1. **Single big docs change** — one change, all 6 deliverables + doc syncs.
   - Pros: one review flow, coherent.
   - Cons: far exceeds 400-line budget; risky review; violates review-workload guard.
   - Effort: High.
2. **Per-deliverable slices in one chained change** — `fase-18-documentation` with ordered slices: P0 ruff fix + API reconciliation → technical manual → architecture rewrite → user manual → install guides → contribution guides (each slice its own PR in a chain).
   - Pros: respects 400-line budget; each slice independently reviewable; proposal/design can reuse one spec family.
   - Cons: longer chain; slice boundaries need care.
   - Effort: Medium (sliced).
3. **Separate small changes per deliverable** — e.g. `fase-18-api-docs`, `fase-18-technical-manual`, etc.
   - Pros: smallest review units; per-doc traceability.
   - Cons: 5–6 orchestrated changes; heavier SDD overhead per doc; phase-level DoD split across changes.
   - Effort: Medium (more process).

### Recommendation

**Approach 2** — one change `fase-18-documentation`, sliced per deliverable (chained PRs). Matches F16/F17 precedent (single change per fase, sliced PRs), protects review budget, and keeps the roadmap DoD (all 6 deliverables) under one verify/archive cycle. Include the ruff P0 slice (17 auto-fixable of 26) to unblock `verify.build_command`, and explicitly record the optuna/env and perf-baseline items as out-of-scope inconsistencies per the proposal rule.

## 9. Risks (summary)

- Scope explosion → slicing mandatory; confirm delivery strategy (`auto-chain` recommended).
- Language ambiguity → confirm Spanish docs / English SDD artifacts at proposal.
- API doc re-drift → decide truth source + optional CI contract test in design.
- optuna + LICENSE decisions → owner calls, not to be absorbed silently.
- Verify inherits 5 pre-existing failures + failing `ruff check .` → record as inconsistencies; P0 fix recommended.

## 10. Ready for Proposal

**Yes.** The orchestrator should tell the user: Fase 18 is the Documentation phase (6 deliverables), the single biggest gap is the stale/aspirational API_SPECIFICATION.md vs 49 real endpoints, and the change should be sliced per deliverable (chained PRs). Two owner decisions are needed before/at proposal: (a) delivery strategy (`auto-chain` recommended), (b) language of deliverable docs (Spanish recommended per project convention) + optuna/LICENSE calls.