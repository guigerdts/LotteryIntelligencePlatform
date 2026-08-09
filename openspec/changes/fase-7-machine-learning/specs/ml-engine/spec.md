# Spec — Machine Learning Engine (`ml-engine`)

**Change**: `fase-7-machine-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Artifact**: spec (this change) — new capability `ml-engine` (full spec for archive merge).

## Purpose

A deterministic, metrics-only, anti-leakage training engine. It builds a supervised frame
per lottery where `X` is the fixed-order per-draw feature vector from the active F4
(`feature_snapshots`) snapshot at draw `n`, and `y` is binary per-number participation in
draw `n+1` (D3). Splits are temporal walk-forward (`train ≤ cut < eval`); scikit-learn
trains 5 model families — Random Forest, Extra Trees, Gradient Boosting, SVM, KNN — under
scope `model_set="core-5"` (D1/D5). Results persist as immutable `ml_*` snapshots
mirroring the F3–F6 contract: dedicated schema, canonical SHA-256 fingerprint over
data+params+`ML_GENERATOR_VERSION`, `active|retired|failed` lifecycle, atomic
single-transaction writes, manual-only triggering, multi-lottery. Determinism is
same-environment only (D2). Metrics are quantized to Decimal `Numeric(20,8)` before
checksum and persistence; float NEVER enters a fingerprint, checksum, or stored value;
model weights are NEVER persisted (D4). The engine consumes ONLY its own Provider
Protocols — never the F5 `probability_service` adapter (latent `models.stat_value` bug)
— and dispatches via a dict registry with no DAG (D5). XGBoost/LightGBM/CatBoost are
declared `future-ml` but never scheduled; `/ml/predict`, `/ml/ranking`, weights, and
optimization are out of scope of this change (proposal §2).

Engine-level requirements are `MLE-01..12`; per-model contracts are `ME-01..05`.

## Requirements

### MLE-01: Independent `ml_*` Schema (D4)

The engine SHALL persist to a dedicated `ml_snapshots` (header) + `ml_metrics` (normalized
payload: `model_id, model_version, number, metric_name, value, params_json`) schema,
mirroring `stat_snapshots`/`prob_snapshots`. It MUST NOT reuse `datasets` or any
`stat_*`/`feature_*`/`prob_*`/`graph_*` table. `value` SHALL be `Numeric(20,8)` Decimal;
no float columns. `params_json` SHALL hold hyperparameters only — never weights.

#### Scenario: writes confined to ml_*
- GIVEN a completed training run over existing draws
- WHEN it commits
- THEN only `ml_*` rows are written; no Core, `stat_*`, `feature_*`, `prob_*`, or
  `graph_*` row changes.

#### Scenario: weights never persisted
- GIVEN a trained Random Forest model
- WHEN the snapshot payload is inspected
- THEN only Decimal-quantized metrics and hyperparameter JSON exist; no serialized model
  bytes (joblib/pickle) in any column or table.

### MLE-02: Strict Read-Only vs Other Engines

The engine MUST NOT modify `lottery`, `draw`, `draw_numbers`, `super_number`, `dataset*`,
`stat_*`, `feature_*`, `prob_*`, or `graph_*`. Writes target `ml_*` only; reads are
passive and never trigger training.

#### Scenario: all non-ml rows unchanged
- GIVEN a training run and concurrent reads
- WHEN both execute
- THEN all Core and prior-engine rows are byte-identical before and after.

### MLE-03: Data Contract & Walk-Forward Split (D3)

`X` SHALL be the feature vector from the active `feature_snapshots` at draw `n` in fixed
feature order; `y` SHALL be `1` when number `k` participates in draw `n+1`, else `0` —
one target per number per family. Splitting SHALL be temporal walk-forward: training draws
`≤ cut`, evaluation draws `> cut`, with `cut` declared per run. A split where any
evaluation row precedes `cut` MUST be rejected (anti-leakage, EC-02).

#### Scenario: temporal split trains and evaluates
- GIVEN a lottery with draws 1..100 and `cut=80`
- WHEN a `train` run executes
- THEN each model trains on rows for draws 1..80 and metrics are computed only on draws
  81..100.

#### Scenario: shuffled split rejected
- GIVEN a candidate split interleaving evaluation rows before `cut`
- WHEN the split validator runs
- THEN the run fails fast with a leakage error and no snapshot is written.

### MLE-04: `scikit-learn` Only, Seeds Fixed (D1/D2)

The engine SHALL train exactly the 5 executed families with scikit-learn; XGBoost,
LightGBM, CatBoost remain declared-but-unexecuted. Trainers MUST fix
`random_state=0` (or an equally deterministic seed where the estimator offers no
random_state) and consume the MLE-03 fixed feature order. Cross-environment byte drift is
not claimed — determinism gates at same-environment reruns (EC-01).

#### Scenario: seeded training
- GIVEN identical input frames in the same environment
- WHEN the same model trains twice
- THEN both runs produce identical quantized metrics and checksum.

#### Scenario: allowlist bounded to scikit-learn
- GIVEN `pyproject.toml` after F7 deps land
- THEN `scikit-learn` (with `numpy`) is exact-pinned in the allowlist; `xgboost`,
  `lightgbm`, `catboost`, `networkx` are absent from installable deps.

### MLE-05: Determinism & Quantization Contract (D2/D4, EC-03)

`input_fingerprint` SHALL be canonical SHA-256 over {draws/data identity, hyperparameters,
feature order, `ML_GENERATOR_VERSION`}; checksum SHALL be canonical SHA-256 over the
QUANTIZED metric payload only. Float MUST NEVER enter a fingerprint, checksum, or
persisted value; canonical JSON is `sort_keys=True`.

#### Scenario: identical rerun matches
- GIVEN two runs on identical inputs in the same environment
- WHEN both complete
- THEN `input_fingerprint` and `checksum` are identical.

#### Scenario: float excluded from checksum
- GIVEN raw float metric values from a completed run
- WHEN the checksum is computed
- THEN only Decimal-quantized `Numeric(20,8)` values feed the digest; raw floats never
  persist.

### MLE-06: Provider Protocols Only — No F5 Reuse (D5)

The engine SHALL read through its own `DrawProvider`, `FeatureProvider`, and
`StatSnapshotProvider` Protocols. It MUST NOT import concrete `probability_service`
internals — specifically the F5 `_StatsReaderAdapter` (imports the nonexistent
`backend.app.models.stat_value`) — and MUST NOT reuse it. A missing feature/snapshot
SHALL resolve as `SNAPSHOT_NOT_FOUND`, never zero-guessed.

#### Scenario: F5 latent bug does not affect ML
- GIVEN the F5 `probability_service` adapter is known-broken
- WHEN the ML path resolves statistics
- THEN it reads through its OWN adapter and never instantiates the F5 one.

#### Scenario: missing snapshot signals absence
- GIVEN no active feature snapshot for the requested lottery
- WHEN the training read path resolves X
- THEN it surfaces `SNAPSHOT_NOT_FOUND` and no training is attempted.

### MLE-07: Registry & Scope `model_set="core-5"` (D5, EC-02)

The registry SHALL dispatch on `model_set`: `core-5` registers the 5 executed families;
`future-ml` registers XGBoost/LightGBM/CatBoost as declared-but-not-executed (FES-08
precedent) — they are versioned but never scheduled. Family-name → builder is dict
dispatch, no DAG; an unknown family fails fast at registration.

#### Scenario: core-5 executes; future-ml stays declared
- GIVEN the registry is loaded
- WHEN a `train` for `model_set="core-5"` executes
- THEN exactly the 5 executed families produce rows; future-ml families produce none.

#### Scenario: unknown family rejected
- GIVEN a registry request for an unregistered family
- WHEN it is registered/requested
- THEN the registry fails fast listing the known families.

### MLE-08: Snapshot Lifecycle & Atomicity

`ml_snapshots` SHALL hold exactly one `active` per `(lottery_id, model_set)`; a successful
run writes the new version and retires the old active IN the same transaction. On any
failure the transaction rolls back and ONLY a terminal `failed` header is persisted —
never `active`/`partial`; `is_locked` is set on commit.

#### Scenario: replace retires, failure marks failed
- GIVEN an active snapshot
- WHEN a new training run succeeds
- THEN the old row retires atomically in the same commit; on failure only a `failed`
  header exists and no payload rows are written.

#### Scenario: idempotent incremental
- GIVEN an active snapshot and `scope="incremental"`
- WHEN a retrain with identical input executes
- THEN a matching fingerprint returns the existing snapshot — no duplicate version.

### MLE-09: No Scheduler — Manual Only (API/CLI parity, EC-04)

Generation SHALL be manual (CLI `lip ml train` / API `POST /ml/train`), never during
import. Reads (`GET /ml/models`, `GET /ml/metrics`) MUST answer from stored `ml_*` and
MUST NOT precompute; a missing snapshot SHALL map to 404 `SNAPSHOT_NOT_FOUND`.

#### Scenario: read never trains
- GIVEN a lottery with no snapshot
- WHEN a read targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and no training is triggered.

### MLE-10: Migration & Non-Destructive Rollback (EC-01)

Migration `0009_ml_tables` (`down_revision = "0008_graph_tables"`) SHALL add the
`ml_*` tables; downgrade MUST drop ONLY `ml_*`.

#### Scenario: rollback is non-destructive
- GIVEN a DB with Core + prior engine tables
- WHEN migration 0009 is downgraded
- THEN `ml_*` is dropped and Core/`stat_*`/`feature_*`/`prob_*`/`graph_*` remain intact.

### MLE-11: Multi-Lottery

Every snapshot SHALL be scoped by `lottery_id`; lotteries are trained independently.

#### Scenario: per-lottery isolation
- GIVEN two lotteries A and B with differing rules/draws
- WHEN both are trained
- THEN their snapshots and metrics share no rows; each uses its own lottery's rules.

### MLE-12: Empty / 0-Draw Handling

An empty live DB is an acceptance constraint, not an implementation blocker: a 0-draw /
no-active-snapshot state SHALL be handled gracefully (clean `validation_error` or
`data not available`), never a crash; the behavior SHALL be exercised with fixture tests.

#### Scenario: empty state is graceful
- GIVEN a live DB with no draws
- WHEN a training request needs the frame
- THEN the response is a clean validation error, never a stack trace, and no snapshot is
  written.

---

## Per-Model Contracts (ME-01..05)

All ME contracts share: per-number target, fixed feature order (MLE-03), fixed seed, same-env
determinism, Decimal-quantized metrics (MLE-05), no weights, scope `core-5` (MLE-07).

### ME-01: Random Forest

The engine SHALL train a Random Forest classifier per target number, `random_state=0`.

#### Scenario: RF metrics persisted
- GIVEN a valid core-5 window
- WHEN train completes
- THEN RF metrics are persisted with versioned `model_version` and a matching checksum.

#### Scenario: RF same-input rerun identical
- GIVEN an identical input frame
- WHEN RF retrains in the same environment
- THEN its quantized metrics and checksum are identical.

### ME-02: Extra Trees

The engine SHALL train an Extra Trees classifier per number, `random_state=0`, same family
contract (seed, metrics, versioning).

#### Scenario: Extra Trees disclosed
- GIVEN a valid core-5 window
- WHEN ET trains
- THEN per-number metrics are persisted, deterministically identical on replay.

### ME-03: Gradient Boosting

The engine SHALL train a Gradient Boosting classifier with `random_state` fixed by
registered defaults.

#### Scenario: seeded Boolean replay
- GIVEN the same configuration and draws
- WHEN training runs twice
- THEN the same environment yields identical quantized metrics and checksum.

### ME-04: Support Vector Machine

The engine SHALL train an SVM classifier (`random_state=0` where the estimator supports
one) per number.

#### Scenario: SVM metrics persisted
- GIVEN a valid core-5 window
- WHEN SVM completes
- THEN its quantized metrics land in a single committed snapshot.

### ME-05: K-Nearest Neighbors

The engine SHALL train a KNN classifier — deterministic by construction, no seed required.

#### Scenario: KNN stable checksum
- GIVEN identical frames
- THEN KNN metrics serialize to the same quantized checksum across runs.

---

**Note**: New capability created at archive from change delta `fase-7-machine-learning`.
Engine requirements `MLE-01..12` + per-model contracts `ME-01..05` follow the
probability-engine spec skeleton (PES/PM parity) exactly as the exploration prescribed.
Backend API/CLI parity surface is specified in the sibling delta
`specs/backend/spec.md` (modifies REQ-10/11/12).