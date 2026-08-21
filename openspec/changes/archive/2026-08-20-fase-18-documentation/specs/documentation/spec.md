# Spec — Documentation (`documentation`)

**Change**: `fase-18-documentation` · **Store**: `hybrid` · **Date**: 2026-08-20

## Purpose

Reconcile all project docs with verified codebase reality; add an anti-drift contract test. Deliverables Spanish; spec English. Delivery: chained PRs per slice S0–S7, ≤400 lines, stacked to main.

## Requirements Overview

| ID | Requirement | Slice | Priority |
|----|-------------|-------|----------|
| DOC-001 | API spec reconciliation + anti-drift | S1 | P0 |
| DOC-002 | Architecture doc rewrite | S2 | P0 |
| DOC-003 | Technical manual | S3 | P0 |
| DOC-004 | User manual | S4 | P0 |
| DOC-005 | Installation guides | S5 | P0 |
| DOC-006 | Contribution guides | S6 | P1 |
| DOC-007 | Aux docs sync | S7 | P0 |
| DOC-008 | Ruff P0 fix | S0 | P0 |
| DOC-009 | Cross-doc consistency | S0–S7 | P0 |
| DOC-010 | Out-of-scope debt registered | S0–S7 | P1 |

## Requirements

### DOC-001: API Spec Reconciliation (S1)

`API_SPECIFICATION.md` MUST document exactly the real surface (49 paths / 53 ops, 14 routers, incl. `/graph/*`, `/meta/*`, `/gen/*`, `/health`, `/version`) and MUST NOT document endpoints absent from live OpenAPI (e.g. `/ml/predict`, `/dl/*`). The path/op reference SHALL be generated from live OpenAPI via `docs/api/generate_reference.py`; a contract test SHALL assert documented paths equal OpenAPI paths.

#### Scenario: contract test green
- GIVEN generator and contract test
- WHEN pytest runs `test_docs_contract.py`
- THEN documented paths equal OpenAPI (49/53), no fictional endpoint remains

#### Scenario: new router detected
- GIVEN a router added without doc update
- WHEN the contract test runs
- THEN it fails, listing the undocumented path

### DOC-002: Architecture Doc Rewrite (S2)

`SYSTEM_ARCHITECTURE.md` MUST be rewritten from Draft to current reality: real module layout, engine seams, snapshot lifecycle, alembic head `0016`, CLI `lip`, frontend tree — zero "Draft" flags, zero pre-implementation fase references, every claim resolving to source.

#### Scenario: draft removed
- GIVEN the rewritten document
- WHEN grepped for "Draft" and fase references
- THEN none are found

#### Scenario: claims resolve to code
- GIVEN an architecture claim (modules, alembic, CLI, routes)
- WHEN checked against source and config
- THEN the claim matches real state

### DOC-003: Technical Manual (S3)

`MANUAL_TECNICO.md` MUST cover all 12 engines, CLI `lip` commands, `LIP_*` config, DB/migrations, and observability, verified against source. It MUST NOT document commands, config vars, or modules that do not exist.

#### Scenario: engine coverage
- GIVEN the 12 engine module dirs
- WHEN the manual is audited
- THEN each engine has a section grounded in its module

#### Scenario: config and CLI verified
- GIVEN a documented `LIP_*` var or `lip` subcommand
- WHEN checked against `config.py` and `cli.py`
- THEN it exists, else non-compliant

### DOC-004: User Manual (S4)

`MANUAL_USUARIO.md` MUST cover every frontend route in `App.tsx` (12 pages + 404) matching real components, plus CLI usage with runnable examples. It MUST NOT describe pages that do not exist.

#### Scenario: page parity
- GIVEN the route table in `App.tsx`
- WHEN the manual is audited
- THEN every route has a section, no invented page exists

#### Scenario: CLI example runnable
- GIVEN a documented CLI example
- WHEN executed against the real CLI
- THEN it produces the described output

### DOC-005: Installation Guides (S5)

`INSTALL.md`, `backend/README.md`, `frontend/README.md` MUST reproduce a fresh install — backend (uv/venv + alembic to head 0016), frontend (npm), DB init — using real commands from `pyproject.toml`, `package.json`, `alembic.ini`.

#### Scenario: fresh install
- GIVEN a clean environment
- WHEN following the guides step by step
- THEN backend serves, frontend builds, DB migrates to head 0016

#### Scenario: commands exist verbatim
- GIVEN any documented command
- WHEN checked against project manifests
- THEN it appears verbatim in the source of truth

### DOC-006: Contribution Guides (S6)

`CONTRIBUTING.md` MUST document branch/PR/commit conventions (conventional commits, no AI attribution), ruff + pytest gates, the SDD workflow, and the 400-line review budget, consistent with `AGENTS.md` and repo history. LICENSE/CHANGELOG status MUST reflect the owner decision; documented absence is acceptable.

#### Scenario: conventions match practice
- GIVEN CONTRIBUTING.md
- WHEN compared with git history and AGENTS.md
- THEN documented conventions match actual practice

#### Scenario: license decision recorded
- GIVEN no LICENSE file in the repo
- WHEN CONTRIBUTING.md is published
- THEN the absence or decision is documented, not silently ignored

### DOC-007: Aux Docs Sync (S7)

`DATABASE_SCHEMA.md` MUST reference migrations 0001–0016 and the `exp_*`/`bt_*`/`ml_*`/`opt_*`/`graph_*` tables; `PROJECT_STATUS.md` MUST record F12–F17; `ENGINE_SPECIFICATIONS.md` MUST correct Section 10 (DL — no router mounted) and generator claims to real state.

#### Scenario: migrations referenced
- GIVEN the alembic versions listing (0001–0016)
- WHEN DATABASE_SCHEMA.md is audited
- THEN every migration is referenced consistently

#### Scenario: stale status corrected
- GIVEN git log F12–F17
- WHEN PROJECT_STATUS.md is audited
- THEN F12–F17 recorded, no stale closure date remains

### DOC-008: Ruff P0 Fix (S0)

The 26 pre-existing ruff errors across 16 files MUST be fixed mechanically (I001, E501, F841, B007) with no behavior change; `ruff check .` MUST exit 0 on src and tests.

#### Scenario: gate green
- GIVEN the mechanical fixes applied
- WHEN `ruff check .` runs
- THEN it exits 0 with no errors

#### Scenario: no behavior change
- GIVEN the S0 commit
- WHEN the backend suite runs
- THEN no new failures beyond the 5 recorded optuna-absent failures

### DOC-009: Cross-Doc Consistency

All F18 docs MUST share one verified baseline (49/53 API, 16 migrations, 12 engines, 13 routes, ruff clean) and MUST be mutually consistent; none MAY invent endpoints, modules, commands, or config.

#### Scenario: single baseline
- GIVEN the verified baseline table
- WHEN all docs are cross-audited
- THEN the same facts and numbers appear consistently

#### Scenario: no invented content
- GIVEN any doc claim
- WHEN traced to source (code, config, routes, migrations)
- THEN it resolves to reality, else non-compliant

### DOC-010: Out-of-Scope Debt Registered

Accepted debt MUST be documented: 5 `tests/opt` failures (optuna not in venv; uv.lock stale), perf-harness baselines (owner: never touch), F17 coverage/CI untouched. Docs MUST reflect real measured state (backend 91.88%, frontend 95.22%, report-only gates).

#### Scenario: debt recorded
- GIVEN the F18 docs
- WHEN searched for optuna, uv.lock, perf-baseline mentions
- THEN they appear as accepted debt with owner decisions

#### Scenario: baselines untouched
- GIVEN perf-harness baselines in config
- WHEN docs reference performance
- THEN measured values cited as-is, baselines not modified