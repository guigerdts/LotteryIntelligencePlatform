# Delta for ML Engine (`ml-engine`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slice**: S4 — engine-level per-number fit parallelization (D2). References requirement IDs from the fase-7 `ml-engine` spec delta (the ML engine main spec is archived under `fase-7-machine-learning/specs/ml-engine/`).

## MODIFIED Requirements

### MLE-04: `scikit-learn` Only, Seeds Fixed (D1/D2)

The engine SHALL train exactly the 5 executed families with scikit-learn; XGBoost, LightGBM, CatBoost remain declared-but-unexecuted. Trainers MUST fix `random_state=0` (or an equally deterministic seed where the estimator offers no random_state) and consume the MLE-03 fixed feature order. Cross-environment byte drift is not claimed — determinism gates at same-environment reruns (EC-01). Per-number fits SHALL be parallelizable ONLY at the engine level (one worker per number fit, bounded `ProcessPoolExecutor(max_workers=2)`); the family loop in `MlService.train` SHALL remain serial (atomic per-family transaction). Workers SHALL be pure: NO DB session inside a worker; fit order SHALL be frozen by sorted number; the engine SHALL never shuffle.
(Previously: the 49 per-number fits per family ran strictly sequentially in one thread; parallelization and its boundaries were unspecified.)

#### Scenario: seeded training

- GIVEN identical input frames in the same environment
- WHEN the same model trains twice
- THEN both runs produce identical quantized metrics and checksum.

#### Scenario: allowlist bounded to scikit-learn

- GIVEN `pyproject.toml` after F7 deps land
- THEN `scikit-learn` (with `numpy`) is exact-pinned in the allowlist; `xgboost`, `lightgbm`, `catboost`, `networkx` are absent from installable deps.

#### Scenario: parallel fits bounded and pure (S4/D2)

- GIVEN a training run over 49 numbers
- WHEN `MlEngine.train` executes the per-number fits
- THEN they run on ≤2 processes, one fit per worker, no DB session in any worker, results keyed by sorted number

#### Scenario: family loop stays serial (S4/D2)

- GIVEN `MlService.train` orchestrating 5 families
- WHEN training runs
- THEN the family loop remains serial, preserving the atomic per-family transaction

### MLE-05: Determinism & Quantization Contract (D2/D4, EC-03)

`input_fingerprint` SHALL be canonical SHA-256 over {draws/data identity, hyperparameters, feature order, `ML_GENERATOR_VERSION`}; checksum SHALL be canonical SHA-256 over the QUANTIZED metric payload only. Float MUST NEVER enter a fingerprint, checksum, or persisted value; canonical JSON is `sort_keys=True`. A serial-vs-parallel `TrainResult` parity test (checksum + fingerprint + quantized metrics) SHALL be byte-identical — a GF-1 violation blocks the slice.

#### Scenario: identical rerun matches

- GIVEN two runs on identical inputs in the same environment
- WHEN both complete
- THEN `input_fingerprint` and `checksum` are identical.

#### Scenario: float excluded from checksum

- GIVEN raw float metric values from a completed run
- WHEN the checksum is computed
- THEN only Decimal-quantized `Numeric(20,8)` values feed the digest; raw floats never persist.

#### Scenario: serial-vs-parallel parity byte-identical (S4)

- GIVEN the same training run once serial and once parallel
- WHEN both complete
- THEN `TrainResult` checksum, fingerprint, and quantized metrics are byte-identical
- AND any byte difference blocks the slice (GF-1 gate)

#### Scenario: training targets met (S4)

- GIVEN the exact commands `pytest tests/ml -q -k test_train_basic --durations=1` and `pytest tests/ml -q -k test_engine_train_basic --durations=1`
- WHEN measured after S4
- THEN `test_train_basic` is ≤4.5 s (baseline 8.18 s) and `test_engine_train_basic` is ≤3.0 s (baseline 5.37 s), proposal §5