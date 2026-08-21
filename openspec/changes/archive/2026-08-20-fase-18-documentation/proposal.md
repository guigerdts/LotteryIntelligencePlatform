# Proposal: Fase 18 — Documentación

- Change: `fase-18-documentation`
- Status: **proposed**
- Store: **hybrid** (engram + openspec)
- Date: 2026-08-20
- Source: [exploration.md](./exploration.md) (complete; measurements, debt classification), IMPLEMENTATION_ROADMAP.md Fase 18, live code verification
- Owner decisions baked in: deliverable docs in **Spanish** (SDD artifacts English); delivery **auto-chain** (stacked-to-main); no optuna/deap install; perf baselines untouched; F17 coverage/CI untouched.

---

## 1. Executive summary

Fase 18 reconciles documentation with the real codebase. The single biggest gap: `API_SPECIFICATION.md` is stale/aspirational (~15 fictional endpoints, ~15 real paths missing) vs. the live OpenAPI surface of **49 paths / 53 ops**. Every deliverable is derived from verified reality (this proposal re-probes: OpenAPI 49/53 confirmed via `backend.app.main.create_app().openapi()`; ruff 26 errors / 17 auto-fixable confirmed; no LICENSE/CHANGELOG convention in repo confirmed). Delivery is sliced per deliverable into chained PRs (`auto-chain`); a P0 ruff hygiene slice unblocks `verify.build_command`; optuna, perf baselines, and coverage/CI changes stay out of scope with recorded inconsistencies.

## 2. Intent

Six roadmap deliverables (API, manual técnico, manual de usuario, arquitectura actualizada, guías de instalación, guías de contribución) plus aux-doc sync. Problem: docs lie about the product — API spec documents non-existent endpoints, SYSTEM_ARCHITECTURE is a pre-implementation Draft, DATABASE_SCHEMA predates migrations 0001–0016, PROJECT_STATUS is stale (closed 2026-08-10, missing F12–F17), no user/technical/install/contribution docs exist. Goal: every doc reflects real code (endpoints, modules, commands, config, schema), with a drift-prevention mechanism for the API reference.

## 3. Verified reality baseline (re-probed 2026-08-20)

| Metric | Value | Verification |
|---|---|---|
| API surface | 49 paths / 53 ops, 14 routers | `create_app().openapi()` (backend.app.main) |
| Backend | 28 module dirs, 23,643 LOC, CLI `lip`, alembic head `0016` | code inspection (exploration) |
| Frontend | 13 pages, 15 components, 6 charts, 13 services, 2 stores, 7,664 LOC | exploration |
| ruff | **26 errors** (7 src: `api/v1/meta.py`, `cli.py:958`, `meta/normalization.py`, `meta/types.py`, `schemas/meta.py`; 19 tests: `tests/meta/*`, `tests/probability/*`, `test_migrations.py:696`), 17 auto-fixable | `ruff check .` (2026-08-20) |
| tests/opt | 124 passed / 5 failed (optuna missing from venv) | exploration probe |
| LICENSE/CHANGELOG | **None** — no file, no git history, no README reference | repo+git audit |
| Docs | 12 root `.md`, 4,548 lines, no `docs/` dir | exploration |

## 4. Scope

### In Scope — 8 slices (each → own chained PR; split if >400 authored lines)

| # | Deliverable | Target file(s) | Source of truth | Acceptance | Est. size |
|---|---|---|---|---|---|
| S0 | Ruff P0 fix (chore) | 16 files (7 src / 9 test files) | `ruff check .` output | `ruff check .` exits 0; no behavior change | ~40 lines |
| S1 | API spec reconciliation + anti-drift | `API_SPECIFICATION.md` (rewrite), `docs/api/generate_reference.py` (new), `backend/tests/api/test_docs_contract.py` (new) | Live OpenAPI (49/53); `backend/src/backend/app/api/v1/*` routers | Every documented path exists in OpenAPI and vice-versa (contract test green); fictional endpoints removed; `/graph/*`, `/meta/*`, `/gen/*`, `/health`, `/version` added | ~700 lines docs + ~150 code → **2 PRs** |
| S2 | Architecture updated | `SYSTEM_ARCHITECTURE.md` (rewrite Draft→current) | 28 modules, engine seams, `backend.app.main:create_app`, alembic 0016, frontend tree | 0 fase references; mirrors real layering & snapshot lifecycle | ~600 lines → **2 PRs** |
| S3 | Technical manual (new) | `MANUAL_TECNICO.md` | Engines (`statistics`, `probability`, `feature_engineering`, `graph`, `ml`, `dl`, `opt`, `backtesting`, `experiments`, `meta`, `generators`, `ai`), `cli.py`, `config.py` (LIP_* env), alembic, `api/errors.py` | Covers all 12 engines + CLI `lip` commands + config vars, verified against source | ~900 lines → **3 PRs** |
| S4 | User manual (new) | `MANUAL_USUARIO.md` | 13 frontend pages + CLI usage | Page-by-page guide matching real routes/components; CLI examples runnable | ~650 lines → **2 PRs** |
| S5 | Installation guides | `INSTALL.md` (new), `backend/README.md` (new), `frontend/README.md` (new) | `pyproject.toml`, `uv.lock`, `alembic.ini`, `package.json`, `vite.config`, scripts | Reproducible fresh install (backend + frontend + DB) | ~350 lines → **1 PR** |
| S6 | Contribution guides | `CONTRIBUTING.md` (new); LICENSE/CHANGELOG per open question | AGENTS.md, repo commit history, openspec/config.yaml, F16/F17 precedents | Branch/PR/commit conventions, ruff+pytest, SDD workflow, review budget documented | ~300 lines → **1 PR** |
| S7 | Aux docs sync | `DATABASE_SCHEMA.md`, `PROJECT_STATUS.md`, `ENGINE_SPECIFICATIONS.md` | alembic 0001–0016, `git log` F12–F17, real DL/generator state | Migrations referenced; F12–F17 recorded; Section 10 DL corrected | ~350 lines → **1 PR** |

### Out of Scope (non-goals)

- **Perf harness baselines** (F17 config; owner: never touch — docs may reference measured values as-is).
- **optuna/deap install** — 5 `tests/opt` failures stay out-of-scope debt (env fix, F16/F17 precedent).
- **F17 coverage/CI changes** — `ci.yml`, `performance.yml`, coverage-history.json, report-only gates untouched (docs reflect real state: backend 91.88%, frontend 95.22%, E2E 1/1).
- **Production behavior changes / new features** — no backend/frontend runtime code beyond S0/S1 support tooling.
- **Full-suite green** — verify inherits the 5 opt failures as recorded inconsistency.

## 5. Capabilities

### New Capabilities
- `documentation`: API reference accuracy (contract test vs live OpenAPI), technical manual, user manual, architecture doc, installation/contribution guides, aux-doc sync. Requirements will cover: docs MUST match real endpoints/modules/commands; API reference MUST pass a path-parity contract test.

### Modified Capabilities
- **None** — no runtime behavior requirements change. S0 is hygiene; S1's contract test guards docs, not backend semantics.

## 6. Approach

- **API source of truth (recommended: HYBRID)**: curated guide sections (envelope, errors, auth, conventions) + **generated** path/operation reference from a small script rendering `create_app().openapi()` into markdown + a pytest **contract test** (`test_docs_contract.py`) asserting documented paths == OpenAPI paths (anti-drift). Rationale: pure manual re-drifts (proven — API_SPEC is stale today); pure generated is not prose-friendly. **Scoped code change flagged**: S1 adds ~150 lines of support code (generator script + one test file) — it does not touch F17 CI/coverage config; the test runs inside the existing pytest suite (report-only coverage, gate `false`).
- **Ruff decision: INCLUDE as S0/P0.** All 26 errors are pre-existing debt (working tree clean; files from F4/F9/F12-era code); fixes are mechanical (I001, E501, F841, B007) — safe, local, no behavior change, and coherent with F18 (docs phase must leave `verify.build_command: ruff check .` green). 17 auto-fixable via `ruff check --fix`; remaining 9 manual (line-length wraps). Not a material scope change.
- **LICENSE/CHANGELOG**: no repo convention exists → flagged as ONE open question (below); S6 will not block on it, using a decision point.
- **Slice order**: S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 (each independent; S1/S2/S3/S4 split into 2–3 chained PRs per 400-line budget). Delivery `auto-chain` stacked-to-main.

## 7. Affected Areas

| Area | Impact | Description |
|---|---|---|
| `API_SPECIFICATION.md` | Rewrite | 49/53 real paths; remove ~15 fictional, add ~15 missing |
| `SYSTEM_ARCHITECTURE.md` | Rewrite | Draft → current (28 modules, engine seams, alembic 0016) |
| `MANUAL_TECNICO.md`, `MANUAL_USUARIO.md`, `INSTALL.md`, `CONTRIBUTING.md`, `backend/README.md`, `frontend/README.md` | New | F18 deliverables |
| `DATABASE_SCHEMA.md`, `PROJECT_STATUS.md`, `ENGINE_SPECIFICATIONS.md` | Modified | Sync to migrations 0001–0016, F12–F17, real DL/generator state |
| `backend/src/backend/app/{api/v1/meta.py, cli.py, meta/normalization.py, meta/types.py, schemas/meta.py}` + 9 test files | Modified (S0) | Ruff hygiene only — no behavior change |
| `docs/api/generate_reference.py`, `backend/tests/api/test_docs_contract.py` | New (S1) | OpenAPI→markdown generator + path-parity contract test |

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Doc size >400 lines per PR (S1–S4) | High | Sliced chained PRs (2–3 per deliverable), `auto-chain` stacked-to-main |
| API re-drift after rewrite | Med | S1 contract test (path parity) in pytest suite |
| Docs inconsistency across 8 slices | Med | All slices verify against same baseline table (§3); S7 reconciliation pass |
| ruff fix touches 16 files | Low | Mechanical only; `ruff check .` green is the gate |
| LICENSE absence blocks S6 | Med | Open question; CONTRIBUTING references decision point, non-blocking |

## 9. Rollback Plan

Per-slice revert (each slice is one chained PR): `git revert <slice-commit>` — docs-only slices are additive/rewrite of `.md` files, zero runtime impact. S0 revert restores the 26 errors (no behavior delta). S1: remove contract test + generator script; keep docs (reverts to status quo ante drift). S7: `git revert` restores prior aux docs. No migrations, no data, no production code touched → rollback is commit-level only.

## 10. Dependencies

- F17 archive (`cde0b81`) — closed; no code dependency.
- S1: FastAPI OpenAPI at runtime import (`backend.app.main:create_app`) — no new packages.
- S0: `ruff` (already pinned; `backend/.venv`).
- Open question (non-blocking): LICENSE/CHANGELOG decision before S6 finalize.

## 11. Success Criteria

- [ ] `ruff check .` exits 0 (S0) with no test regressions.
- [ ] `test_docs_contract.py` green: documented paths == OpenAPI paths (49/53).
- [ ] API_SPECIFICATION.md has zero fictional endpoints; all 14 routers covered.
- [ ] SYSTEM_ARCHITECTURE.md Draft flag removed; matches real module/DB/CLI state.
- [ ] MANUAL_TECNICO.md covers 12 engines + `lip` CLI + `LIP_*` config; MANUAL_USUARIO.md covers 13 pages.
- [ ] INSTALL.md reproduces fresh backend+frontend+DB setup.
- [ ] CONTRIBUTING.md published; PROJECT_STATUS.md records F12–F17; DATABASE_SCHEMA.md references migrations 0001–0016.
- [ ] All slices ≤400 authored lines; full suite: 1427 passed / 5 pre-existing opt failures recorded as inconsistency.

## 12. Open Questions (genuine, non-blocking)

1. **LICENSE (and CHANGELOG)**: repo has no license file, no changelog convention, no README reference — only the owner can decide. Options: MIT (permissive, matches public docs style) / proprietary notice / defer both and document the absence in CONTRIBUTING. CHANGELOG: create `CHANGELOG.md` starting at F18, or omit. **Proposal proceeds without this; S6 marks a decision point.**

## Key Learnings

1. The API spec gap is quantified: 49 real paths/53 ops vs ~40 documented with ~15 fictional and ~15 missing.
2. All 26 ruff errors are pre-existing mechanical debt (I001/E501/F841/B007) safe to fold in as a P0 slice.
3. No LICENSE or CHANGELOG convention exists in the repo or git history — a genuine owner question.
4. A path-parity pytest contract test is the cheapest anti-drift guard and runs inside the existing report-only suite.
5. Slicing per deliverable with auto-chain keeps every PR within the 400-line review budget.