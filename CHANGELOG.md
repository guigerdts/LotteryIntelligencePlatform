# Changelog

All notable changes to the Lottery Intelligence Platform (LIP).
Format based on Keep a Changelog; versions follow SemVer.
Generated from the real Git history (260 commits, 2026-08-05 → 2026-08-21).

## [Unreleased]

### Fixed
- `GET /api/v1/version` (and the startup log / snapshot `engine_version`) now report `1.0.0`, matching the release manifests; the value was hardcoded to `0.1.0` in `Settings.app_version`.
- Dev-mode API wiring: `vite.config.ts` now proxies `/api` to the backend (`http://127.0.0.1:8000`). Previously `npm run dev` served the SPA fallback HTML for `/api/v1/*` with HTTP 200, producing "Invalid response from server" in the dashboard; E2E/tests masked it by using explicit base URLs and mocks.
- CORS defaults now allow both dev origins (`localhost:5173` and `localhost:5174`) in `Settings.allowed_origins`.
- Probability generation works again end-to-end (`lip probability generate` and `POST /api/v1/probability/generate`): `_DrawReaderAdapter` wrapped `DrawRepository`, which has no `iter_draws()`, crashing with `AttributeError`; it now reads through `StatPayloadRepository.iter_draws`. Unit tests stayed green because they injected a fake provider — new integration tests exercise the adapter against a real session (`tests/probability/test_draw_reader_adapter.py`).
- Graph snapshots now record the real draw-number range in `draws_from`/`draws_to` instead of internal row IDs (e.g. Baloto reports `2091..2100`, consistent with statistics/features snapshots).

Discovered during the post-release manual walkthrough of rc.1. The graph double-snapshot observation was reclassified as expected behavior: two legitimate deterministic runs (dashboard Redes panel POST + CLI) produce identical checksums.

### Changed
- ML and DL training contracts now consume exactly the 8 F4 features that persist as scalar cells: `ML_FEATURE_ORDER` (`ml/features.py`) and `DL_FEATURE_ORDER` (`dl/window.py`) were reduced from 10 ids, dropping FE-07 `decade_distribution` and FE-10 `current_frequency`. Both are mapping-valued, so F4 computes and fingerprints them but never stores cells (design §2/FES-05); demanding them from stored snapshots made real-data training fail with `SnapshotNotFoundError` (ML) or silently zero-fill columns (DL). The unit suites missed it because they fabricate all rows in memory. The DL model input width is now derived from the contract (`N_FEATURES = len(DL_FEATURE_ORDER)`), and docstrings no longer claim `_build_rows` persists every computed value. New seam integration tests lock the persisted-snapshot → reader → matrix/window path (`tests/ml/test_f4_snapshot_seam.py`).

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
- MIT License (applied immediately after tagging; owner decision RC-009).

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

- (empty — feature freeze; fixes only until v1.0.0)
