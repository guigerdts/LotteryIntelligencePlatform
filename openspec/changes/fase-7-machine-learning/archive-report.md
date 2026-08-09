# Archive Report: Fase 7 — Machine Learning Engine

**Change**: fase-7-machine-learning · **Date**: 2026-08-09
**Status**: CLOSED · **Verified**: 2026-08-09

## Executive Summary

Fase 7 delivered a deterministic, metrics-only ML training engine for the Lottery Intelligence Platform. Five scikit-learn families (RF, Extra Trees, Gradient Boosting, SVM, KNN) execute under `model_set="core-5"` with walk-forward validation, anti-leakage enforcement, and atomic snapshot lifecycle. The implementation spans 6 stacked-to-main PRs with 48 ML-specific tests and 512 total tests passing.

## Size:Exceptions

| PR | LOC | Budget | Delta | Justification |
|----|-----|--------|-------|---------------|
| PR4 | 894 | 400 | +494 | Composition root (snapshot_store + providers + ml_service) with atomic transaction management. Splitting would break the active→retired→commit atomicity contract. |
| PR5 | 611 | 400 | +211 | API + CLI with integration coverage. Post-hoc DrawNumber.number bug fix inflated LOC. |

**Conditions met:**
1. ✅ Both exceptions registered in this archive
2. ✅ No artificial refactoring for budget compliance
3. ✅ All MLE/ME requirements maintained
4. ✅ Scope limits preserved (core-5 only, no XGBoost/LightGBM/CatBoost, no /ml/predict, no /ml/ranking, F5 bug out of scope)

## PR Summary

| PR | Content | Prod LOC | Test LOC | Total | Status |
|----|---------|----------|----------|-------|--------|
| PR1 | deps + migration 0009 + ml package + ORM | 264 | 219 | 483 | ✅ Merged |
| PR2 | registry + fingerprint + determinism + splitter | 231 | 202 | 433 | ✅ Merged |
| PR3 | engine + feature_reader + walk-forward | 258 | 147 | 405 | ✅ Merged |
| PR4 | snapshot_store + providers + ml_service | 441 | 453 | 894 | ✅ Merged (size:exception) |
| PR5 | API + CLI + DrawNumber fix | 293 | 318 | 611 | ✅ Merged (size:exception) |
| PR6 | E2E determinism + backend parity | 0 | 214 | 214 | ✅ Merged |

**Total**: 1,487 prod + 1,553 test = **3,040 LOC**

## Verification Results

### Test Suite
- **512 passed, 1 skipped** (full suite parity verified)
- **48 ML-specific tests** across 7 test files
- **3 E2E tests** (determinism, backend parity, statistics parity)

### Ruff
- **Clean** — zero violations after final cleanup commit

### Requirements Compliance

| Requirement | Status |
|-------------|--------|
| MLE-01: No weights persisted | ✅ params_json only |
| MLE-03: Per-number target | ✅ MlMetric.number column |
| MLE-04: scikit-learn only | ✅ pyproject.toml pinned |
| MLE-05: Deterministic fingerprint | ✅ SHA-256 canonical JSON |
| MLE-06: Provider Protocol seams | ✅ DrawHistoryProvider, FeatureSnapshotProvider |
| MLE-07: core-5 only executed | ✅ Registry = {rf, et, gb, svm, knn} |
| MLE-08: Atomic lifecycle | ✅ create→retire→commit; failed terminal |
| MLE-09: No auto-precompute | ✅ Manual-only CLI+API |
| MLE-10: Additive migration | ✅ 0009 creates ml_*; downgrade drops ONLY ml_* |
| D1: Allowlist bounded | ✅ scikit-learn + numpy only |
| D4: Float red line | ✅ Numeric(20,8) Decimal |
| REQ-10: Stats parity | ✅ POST /statistics/generate still 200 |
| REQ-11: Additive surface | ✅ stat_snapshots unchanged after ML train |
| REQ-12: Feature parity | ✅ Feature snapshot untouched |

### Scope Limits

| Limit | Status |
|-------|--------|
| Core-5 only (RF, ET, GB, SVM, KNN) | ✅ Confirmed |
| No XGBoost/LightGBM/CatBoost | ✅ Confirmed (test_no_future_ml_imports) |
| No /ml/predict endpoint | ✅ Confirmed |
| No /ml/ranking endpoint | ✅ Confirmed |
| F5 bug out of scope | ✅ Confirmed (probability_service not touched) |

### Determinism & Safety

| Property | Status |
|----------|--------|
| Byte-determinism | ✅ test_determinism_two_runs |
| Anti-shuffle rejection | ✅ test_anti_shuffle_rejected |
| Walk-forward integrity | ✅ test_engine_walk_forward_respects_cut |
| Fingerprint determinism | ✅ test_fingerprint_deterministic |
| Decimal quantization | ✅ test_bulk_insert_metrics_decimal |
| Lifecycle atomicity | ✅ test_retire_old_active |
| Lifecycle terminal failed | ✅ test_mark_failed |
| Manual-only | ✅ test_manual_only |

## Files Created/Modified

### New Files (ML package)
- `backend/src/backend/app/ml/__init__.py`
- `backend/src/backend/app/ml/version.py`
- `backend/src/backend/app/ml/features.py`
- `backend/src/backend/app/ml/registry.py`
- `backend/src/backend/app/ml/fingerprint.py`
- `backend/src/backend/app/ml/determinism.py`
- `backend/src/backend/app/ml/splitter.py`
- `backend/src/backend/app/ml/engine.py`
- `backend/src/backend/app/ml/feature_reader.py`
- `backend/src/backend/app/ml/snapshot_store.py`
- `backend/src/backend/app/ml/providers.py`

### New Files (Models)
- `backend/src/backend/app/models/ml_snapshot.py`
- `backend/src/backend/app/models/ml_metric.py`

### New Files (Service/API/CLI)
- `backend/src/backend/app/services/ml_service.py`
- `backend/src/backend/app/api/v1/ml.py`
- `backend/alembic/versions/0009_ml_tables.py`

### New Files (Tests)
- `backend/tests/test_ml_pr1.py`
- `backend/tests/test_ml_pr2.py`
- `backend/tests/test_ml_pr3.py`
- `backend/tests/test_ml_pr4.py`
- `backend/tests/test_ml_pr5.py`
- `backend/tests/ml/__init__.py`
- `backend/tests/ml/test_ml_determinism_e2e.py`
- `backend/tests/ml/test_ml_backend_parity.py`

### Modified Files
- `backend/pyproject.toml` — numpy==2.2.6, scikit-learn==1.6.1
- `backend/src/backend/app/models/__init__.py` — MlSnapshot, MlMetric re-exports
- `backend/src/backend/app/api/v1/router.py` — ML router mounted
- `backend/src/backend/app/cli.py` — ml subcommands
- `backend/tests/test_migrations.py` — HEAD_TABLES_0009

## Commits

```
a75cb8d fix(ml): ruff cleanup — unused imports, sort order
66d2f39 feat(ml): add E2E determinism + backend parity tests — PR6
42007c2 feat(ml): add ML engine with API, CLI, and 45 tests — PR1-PR5
```

## Working Tree State
- **Clean** — no uncommitted changes
- **HEAD**: a75cb8d
- **Branch**: main

## Next Steps
- Fase 8 (if applicable) or production deployment
- ML engine is functional and verified; no blocking issues remain
