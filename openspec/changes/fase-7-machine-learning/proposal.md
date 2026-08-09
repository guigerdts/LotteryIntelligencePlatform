# Proposal: Fase 7 — Machine Learning Engine

**Change**: `fase-7-machine-learning` · Store: openspec · Date: 2026-08-09 · Predecessor: exploration

## 1. Intent

Deterministic per-lottery training of 5 model families (RF, Extra Trees, Gradient Boosting, SVM, KNN) on per-draw features; walk-forward anti-leakage split; scikit-learn as first runtime dep; metrics as immutable fingerprinted `ml_*` snapshots (F3–F6 contract).

## 2. Scope

**In**: `app/ml/` — registry (5 executed; XGBoost/LightGBM/CatBoost `future`), wrappers, fingerprint/checksum, determinism, metrics, providers, snapshot store; migration `0009_ml_tables`; `MlService` (idempotent, `active|retired|failed`); `scikit-learn` pin + allowlist; CLI `lip ml train|models|metrics`; API `GET /ml/models`, `POST /ml/train`, `GET /ml/metrics`; migration/determinism/leakage tests.

**Out**: `/ml/predict`, `/ml/ranking` (no predict-in-production); Naive Bayes — excluded; weights/DL/optimization/generator; F5 `stat_value` bug; F3-pending features — skipped.

## 3. Capabilities

- **New** `ml-engine` → `openspec/specs/ml-engine/spec.md` (engine `MLE-..`, per-model `ME-..`)
- **Modified** `backend` REQ-10/11/12 — `ml/*` route+CLI parity (delta)

## 4. Decisions (D1–D6)

**D1 Deps**: `scikit-learn` exact-pinned (numpy/joblib) joins explicit allowlist; signed exception to F6 stdlib gate; `networkx`/xgboost/lightgbm/catboost remain banned.

**D2 Determinism**: `random_state=0`; fixed feature order; canonical fingerprint (data+params+`ML_GENERATOR_VERSION`); same-env rerun ⇒ identical fingerprint/checksum (cross-env not claimed); checksum over quantized metrics.

**D3 Target/leakage**: y = per-number participation in draw `n+1` (binary, one model per family×number); X = F4 features at `n` ± stat/graph scalars; walk-forward (train ≤ cut < eval); leakage test rejects shuffled splits.

**D4 Numeric persistence**: metrics quantize to Decimal `Numeric(20,8)` before checksum/store; no float columns; no weights — `params_json` holds hyperparameters.

**D5 Engine contract**: mirrors `probability/` — own provider Protocols (never `probability_service` adapter), dict-dispatch registry, no DAG, scope `model_set="core-5"`.

**D6 PR chain** (≤400 LOC/PR, stacked-to-main): deps+0009+models (~230), registry+fingerprint+determinism (~380), training+walk-forward (~380), store+service (~320), API+CLI (~330), e2e tests+docs (~350).

## 5. Approach

F5 mirror: pure engine, composition-root service, single atomic write, fingerprint idempotency, `failed` marker, reads served from stored snapshots (404 absent), determinism e2e via two seeded DBs.

## 6. Affected Areas

|Area|Impact|
|---|---|
|`pyproject.toml`, CI|Modified|
|`models/ml_snapshot.py` + `ml_metric.py`, `0009_ml_tables.py`|New|
|`app/ml/**`, `app/services/ml_service.py`|New|
|`api/v1/ml.py`, `schemas/ml.py`, `cli.py`|New/Mod|
|`tests/ml/*`, `test_ml_determinism.py`|New|
|`specs/ml-engine`, README, PROJECT_STATUS|New/Mod|

## 7. Risks

|Risk|L|Mitigation|
|---|---|---|
|Ban-gate relaxation|High|allowlist + pin|
|Cross-env byte drift|Med|same-env gate, quantized checksums|
|Leakage|High|walk-forward + test|
|Decimal fidelity|Low|quantize-before-store|
|F5 adapter trap|Med|own stats seam|

## 8. Rollback Plan

`alembic downgrade` drops only `ml_*`; revert pin + allowlist; remove `app/ml/`, service, routes; all other snapshots untouched.

## 9. Dependencies

F1 draws; F4 feature snapshot (X); F3 stat, F6 graph scalars (optional); `scikit-learn`.

## 10. Success Criteria

- Migration up/down non-destructive; retrain ⇒ identical fingerprint+checksum (same env)
- 5 families + 3 future declared; leak test fails shuffled, passes walk-forward
- No float in columns; metrics Decimal-quantized
- Snapshot-only reads (404), CLI/API parity, pytest+ruff green across the 6 PR chain