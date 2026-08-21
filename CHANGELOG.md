# Changelog

All notable changes to the Lottery Intelligence Platform (LIP).
Format based on Keep a Changelog; versions follow SemVer.
Generated from the real Git history (260 commits, 2026-08-05 → 2026-08-21).

## [1.0.0-rc.1] — 2026-08-21 (Fase 19 — Release Candidate)

Feature freeze for v1.0.0: fixes only until release.

### Fixed
- Backend virtualenv now matches declared runtime deps (`deap==1.4.1`, `optuna==4.0.0`); the 5 tests/opt failures are gone (RC-001).
- `OptimizerProtocol` is now `@runtime_checkable`, enabling the protocol `isinstance` checks used by the opt engine tests.
- `uv lock` is reproducible again: PyTorch CPU index declared in `pyproject.toml`; lock regenerated with `torch==2.13.0+cpu`.
- Frontend suite stabilized under load: sequential file execution + explicit wait budgets; 3 consecutive fully-green runs (137/137).

### Added
- `RELEASE_VALIDATION.md`: full release validation evidence (backend 1434 passed @92% cov, frontend 137×3, E2E 1/1, perf 3/3).
- Performance baselines recalibrated from controlled measurements (cold_start 4.0 s, stats GET 0.015 s, parallel BT 0.17 s) after proving the earlier FAIL was a cold page-cache artifact.

### Changed
- Versions bumped to 1.0.0 in both manifests; PROJECT_STATUS records the RC freeze state.

## Fase 18 — Documentation (2026-08-20)

- API_SPECIFICATION.md reconciled with the real OpenAPI surface (49 paths / 53 ops) via a generator plus an anti-drift contract test (`tests/api/test_docs_contract.py`).
- SYSTEM_ARCHITECTURE.md rewritten from pre-implementation draft to as-built reality (25 packages, ~23.6k LOC, alembic head 0016).
- New manuals: MANUAL_TECNICO.md (12 engine sections), MANUAL_USUARIO.md (all routes + CLI), INSTALL.md, backend/frontend READMEs, CONTRIBUTING.md.
- Aux docs synced to code: DATABASE_SCHEMA.md (migrations 0001–0016), PROJECT_STATUS.md (F12–F17), ENGINE_SPECIFICATIONS.md (DL no-router state).
- Pre-existing ruff errors fixed to zero as slice S0.

## Fase 17 — Testing (2026-08-20)

- Test baseline established and verified: backend coverage 91.88%, frontend 95.22%, E2E core-cycle green.
- Custom performance harness (TEST-006/ADR-6): cold_start, cached_statistics_get, parallel_bt_train ops with baseline/tolerance reporting; NOT a PR gate.
- CI coverage gates report-only with a 3-consecutive-runs promotion rule.

## Fase 16 — Performance (2026-08-19)

- LRU response cache for hot GET endpoints; bounded ProcessPoolExecutor path for backtesting.
- Lazy imports for heavy ML/DL deps at app import time (DLE-17).

## Fase 15 — AI Assistant (2026-08-18)

- Assistant API (`backend.app.api.v1.assistant`) with system status, model catalog, metrics and probability context endpoints; IA dashboard page.

## Fase 14 — Dashboard (2026-08-17)

- React SPA shell: dashboard layout with sidebar navigation, lazy route chunks, error/retry states; 12 feature pages wired to the API contract.

## Fase 13 — Generator Engine (2026-08-16)

- Ticket generation engine (`gen/*` endpoints, CLI `lip gen`) with deterministic seeds and fingerprinted outputs.

## Fase 12 — Graph Engine (2026-08-14)

- Co-occurrence graph analysis over draw numbers (`graph_*` snapshots, `/graph/*` endpoints, CLI `lip graph`).

## Fase 11 — Experiment Engine (2026-08-12)

- Experiment tracking/comparison layer over bt/ml/dl/opt snapshots (`exp_*` tables, polymorphic run references, JSON/CSV export). Registers and compares; never executes engines.

## Fase 10 — Backtesting Engine (2026-08-11)

- Walk-forward backtesting with anti-leakage temporal ordering, lottery-specific metrics, dual benchmark (uniform random + hypergeometric), atomic snapshot lifecycle, manual-only execution.

## Fase 9 — Optimization Engine (2026-08-10)

- Core-4 hyperparameter optimizers: GA (deap), PSO (custom), Bayesian (optuna), SA (custom); quantized Decimal fitness, SHA-256 fingerprints, `opt_*` snapshots.

## Fase 8 — Deep Learning (2026-08-09)

- PyTorch CPU-only MLP+LSTM training with walk-forward splits and byte-identical determinism (GF1); weights stored as custom BLOB format. Inference router intentionally not mounted.

## Fase 7 — Machine Learning (2026-08-09)

- scikit-learn core-5 models (RF, ExtraTrees, GB, SVM, KNN) with walk-forward evaluation, anti-shuffle guards, Decimal(20,8) metrics and `ml_*` snapshots.

## Fase 5 — Probability Engine (2026-08-08)

- Per-number probabilistic prediction snapshots with idempotent generation (G9 determinism, G10 read-only core domain).

## Fase 4 — Feature Engine (2026-08-08)

- F4 rolling features (10 core) with versioned, immutable snapshots and active lifecycle policy.

## Fase 3 — Statistics Engine (2026-08-07)

- Frequencies, gaps and NULL-aware averages; on-demand generation via CLI/API; byte-identical regeneration guarantee.

## Fase 2 — Data Engine (2026-08-06)

- CSV import pipeline: validation, cleaning, normalization, dataset versioning, audit trail (`import_job`, `import_error`).

## Fase 1 — Core Domain (2026-08-06)

- FastAPI foundation: layered hexagonal scaffold, SQLAlchemy entities, alembic migrations, repositories, CRUD, config via pydantic-settings.

## [Unreleased]

- LICENSE selection (pending owner decision).
