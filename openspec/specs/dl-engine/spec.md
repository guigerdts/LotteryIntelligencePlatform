# Spec — Deep Learning Engine (`dl-engine`)

**Change**: `fase-8-deep-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Artifact**: spec (this change) — new capability `dl-engine` (full spec for archive merge), parallel to `ml-engine` (F7 contracts frozen, untouched).

## Purpose

A deterministic, CPU-only PyTorch training engine on windowed sequences (D1/D3/D5/D7):
`X` is a window of `W` consecutive frozen F4 feature vectors ending at draw `n`; `y` is the
F7-identical binary per-number participation in draw `n+1` (F12 comparability). Splits are
window-aware walk-forward (train windows end `≤ cut`, eval windows start `> cut`); MLP + LSTM
execute under `model_set="core-3"`; Transformer/TensorFlow are declared `future-dl` never
scheduled. Results persist as immutable `dl_*` snapshots (dedicated schema, canonical SHA-256
fingerprint over data+params+architecture+seed+window+`DL_GENERATOR_VERSION`, active|retired|
failed lifecycle, atomic single-transaction writes, manual-only). Determinism is same-env
byte-identical: seed 0, `use_deterministic_algorithms(True)`, single thread, float32 — a
non-deterministic op FAILS the run, never degrades it (D3). As an authorized, versioned
exception to F7 MLE-01, model weights ARE persisted to `dl_weights` BLOB in a custom format
(magic + format_version + fingerprint + tensor manifest + raw float32 + SHA-256), ≤16 MiB, no
pickle/joblib, no public load (D2). Training demands ≥100 real draws; below that a clean
`INSUFFICIENT_DATA` with no snapshot (D4). The engine reads only its own Provider Protocols
(MLE-06 parity) and never touches F3–F7.

Engine requirements `DLE-01..16`; per-model contracts `DE-01..02`. Each DLE mirrors an
`ml-engine` requirement where noted (mirror = same contract, adapted to sequences/DL).

## Requirements Overview

| ID | Requirement | Priority | Mirrors |
|----|-------------|----------|---------|
| DLE-01 | Independent `dl_*` schema incl. `dl_weights` | P0 | MLE-01 |
| DLE-02 | Strict read-only vs other engines | P0 | MLE-02 |
| DLE-03 | Target contract: binary per-number n+1 | P0 | MLE-03 |
| DLE-04 | Window & sequence input (W default 10, bounds 2..20) | P0 | new (F7 input is a single vector) |
| DLE-05 | Window-aware walk-forward splitter (anti-leakage) | P0 | MLE-03 (extended) |
| DLE-06 | PyTorch-only, CPU-only, exact pin + signed networkx exception | P0 | MLE-04 |
| DLE-07 | DL determinism: seed 0, deterministic ops, fail-explicit | P0 | MLE-04/05 (extended) |
| DLE-08 | Fingerprint & Decimal-quantized checksum (W in fingerprint) | P0 | MLE-05 |
| DLE-09 | Weights persistence: custom format, ≤16 MiB, validated | P0 | MLE-01 (authorized exception) |
| DLE-10 | Data floor: ≥100 real draws; else INSUFFICIENT_DATA | P0 | MLE-12 |
| DLE-11 | Registry & scope `core-3` + `future-dl` | P0 | MLE-07 |
| DLE-12 | Snapshot lifecycle & atomicity, fingerprint idempotency | P0 | MLE-08 |
| DLE-13 | Provider Protocols only | P0 | MLE-06 |
| DLE-14 | Manual-only surface; `/dl/predict` deferred | P0 | MLE-09 |
| DLE-15 | Multi-lottery | P1 | MLE-11 |
| DLE-16 | Migration `0010` additive; non-destructive rollback | P0 | MLE-10 |

## Requirements

### DLE-01: Independent `dl_*` Schema Incl. Weights Storage

The engine SHALL persist to a dedicated `dl_snapshots` (header) + `dl_metrics` (normalized
payload: `model_id, model_version, number, metric_name, value, params_json`) + `dl_weights`
(see DLE-09) schema, mirroring `stat_*`/`ml_*`. It MUST NOT reuse `datasets`, `ml_*`, or any
Core/`stat_*`/`feature_*`/`prob_*`/`graph_*` table. `value` SHALL be `Numeric(20,8)` Decimal —
no float columns. `params_json` SHALL hold hyperparameters only; model bytes live exclusively
in `dl_weights` (DLE-09).

**Acceptance**
- [ ] A training commit writes rows in `dl_*` only; no other table changes.
- [ ] No serialized bytes exist outside the `dl_weights` BLOB column/table.

#### Scenario: writes confined to dl_*
- GIVEN a completed DL training run over existing draws
- WHEN it commits
- THEN only `dl_*` rows are written; no Core, `ml_*`, `stat_*`, `feature_*`, `prob_*`, or `graph_*` row changes.

#### Scenario: weights live only in dl_weights
- GIVEN a trained MLP with a persisted state dict
- WHEN the snapshot payload is inspected
- THEN `params_json` and `dl_metrics` contain only hyperparameters and Decimal metrics; the state bytes exist ONLY in `dl_weights`.

### DLE-02: Strict Read-Only vs Other Engines

The engine MUST NOT modify `lottery`, `draw`, `draw_numbers`, `super_number`, `dataset*`, `ml_*`, or any prior-engine table. Writes target `dl_*` only; reads are passive and never trigger training.

**Acceptance**
- [ ] All non-`dl_*` rows byte-identical before/after a run under concurrent reads.

#### Scenario: all non-dl rows unchanged
- GIVEN a training run and concurrent reads
- WHEN both execute
- THEN all Core and prior-engine rows are byte-identical before and after.

### DLE-03: Target Contract — Binary Per-Number n+1

`y` SHALL be `1` when number `k` participates in draw `n+1`, else `0` — one target per number
per family, byte-identical semantics to F7 (D5). Draw `N` (last) SHALL have no target. The
target family SHALL remain fixed for F12 Meta Learning comparability.

**Acceptance**
- [ ] For draws 1..N, exactly N−1 label rows per number are produced; the final draw yields none.

#### Scenario: F7-comparable labels
- GIVEN draws 1..100 for a lottery with 6-of-50 rules
- WHEN the frame is built
- THEN each number `k` yields one binary label per frame draw `n ∈ [1, 99]`; draw 100 contributes no label row.

### DLE-04: Window & Sequence Input (W in fingerprint)

`X` SHALL be a sequence of `W` consecutive per-draw F4 feature vectors, each vector in the
frozen F7 canonical feature order, positions ordered `n-W+1 .. n` (oldest→newest); window length
`W` SHALL default to 10, SHALL be restricted to `2..20`, and SHALL be a fingerprint-affecting
hyperparameter. A frame SHALL exist only for draws with a complete window (`n ≥ W`); shorter
histories MUST NOT be zero-padded or excluded silently — the builder SHALL surface a clean
validation error when the configured `W` exceeds available history.

**Acceptance**
- [ ] A window of exactly `W` vectors in canonical order is produced per frame draw; default `W=10`.
- [ ] `W` outside 2..20 is rejected; `W` participates in the fingerprint (DLE-08).

#### Scenario: default window builds
- GIVEN 120 draws and default `W=10`
- WHEN the sequence builder runs
- THEN frame draw `n` yields the 10 vectors for draws `n-9..n`, and frames exist for `n ∈ [10, 119]`.

#### Scenario: out-of-bounds W rejected
- GIVEN a request with `W=1` or `W=25`
- WHEN validation runs
- THEN the run fails fast with a clean validation error; no snapshot or weights are written.

### DLE-05: Window-Aware Walk-Forward Splitter (Anti-Leakage)

Splitting SHALL be temporal and window-aware: every train window MUST end `≤ cut`; every eval
window MUST start `> cut`. A candidate split where any window straddles `cut`, or where
evaluation windows interleave training windows, MUST be rejected with a `LeakageError` and no
snapshot written. `cut` SHALL be declared per run and participate in the fingerprint.

**Acceptance**
- [ ] Straddle and shuffle candidates fail fast with `LeakageError` (RED test).
- [ ] Clean train/eval splits pass; eval windows never contain a draw `≤ cut`.

#### Scenario: clean walk-forward split
- GIVEN 120 draws, `W=10`, `cut=95`
- WHEN the splitter runs
- THEN every train window ends ≤ 95 and every eval window starts ≥ 96; metrics are computed only on eval windows.

#### Scenario: straddling window rejected
- GIVEN a candidate window covering draws 92..101 with `cut=95`
- WHEN the split validator runs
- THEN the run fails fast with `LeakageError` and no snapshot is written.

#### Scenario: shuffled split rejected
- GIVEN an eval window preceding a train window
- WHEN the validator runs
- THEN the run fails fast; no training occurs.

### DLE-06: PyTorch-Only, CPU-Only, Exact Pin + Signed networkx Exception

The engine SHALL train with PyTorch CPU wheels only, exact-pinned (D1), and MUST NOT use
TensorFlow. `torch`'s transitive `networkx`/`sympy`/`jinja2`/`filelock`/`fsspec`/
`typing-extensions` SHALL be accepted ONLY as unsigned-internal transitive deps of the torch
F8 tree (signed exception), never as installable/runtime deps of `app/` code, and MUST NOT be
imported by `app/dl/`. The F7 allowance is unchanged: `xgboost`, `lightgbm`, `catboost`,
`networkx` as installable deps, and `tensorflow` remain banned-declared (`future-dl`).

**Acceptance**
- [ ] `pyproject.toml` pins torch (CPU) exactly; the ban-gate test still rejects installable networkx/tensorflow/xgboost/lightgbm/catboost.
- [ ] `app/dl/` imports only torch (+ numpy/shared utils); no direct `networkx` import.

#### Scenario: torch pinned, ban-gate holds
- GIVEN `pyproject.toml` after F8 deps land
- THEN torch CPU is exact-pinned in the allowlist; installable deps contain no networkx/tensorflow/xgboost/lightgbm/catboost.

#### Scenario: dl code never imports networkx
- GIVEN the dl module import surface
- WHEN the ban-gate test scans it
- THEN no direct `networkx` (or banned-name) import appears; the exception comment marks the torch-transitive relationship.

### DLE-07: DL Determinism — Seed 0, Deterministic Ops, Fail-Explicit

Training SHALL be deterministic on CPU (D3): `seed=0` (`torch.manual_seed(0)`), float32,
`torch.use_deterministic_algorithms(True)`, `torch.set_num_threads(1)`, canonical ordering
(`draw_number`, feature order, `W`). Any non-deterministic operation SHALL make the run FAIL
explicitly (clean terminal `failed` header) — the engine MUST NOT degrade silently. Same-env
reruns SHALL be byte-identical (GF1 gate: identical fingerprint + checksum + metric rows).

**Acceptance**
- [ ] Two seeded CPU reruns on identical inputs produce identical fingerprint, checksum, and metric rows.
- [ ] A non-deterministic op aborts the run with a clear error; no `active` snapshot appears.

#### Scenario: same-env rerun byte-identical
- GIVEN identical inputs and two fresh DBs in the same environment
- WHEN the same training runs on each
- THEN fingerprints, checksums, and quantized metric rows are identical.

#### Scenario: non-deterministic op fails explicitly
- GIVEN a training graph that triggers a non-deterministic operation
- WHEN the run executes under `use_deterministic_algorithms(True)`
- THEN the run aborts with an explicit determinism error and only a terminal `failed` header is persisted.

### DLE-08: Fingerprint & Decimal-Quantized Checksum

`input_fingerprint` SHALL be canonical SHA-256 over `{data_hash, hyperparameters,
architecture, seed, window W, cut, DL_GENERATOR_VERSION}`; `checksum` SHALL be canonical SHA-256
over the Decimal-quantized metric payload only. Float MUST NEVER enter a fingerprint, checksum,
or persisted value; canonical JSON is `sort_keys=True` (MLE-05 parity).

**Acceptance**
- [ ] Identical reruns share fingerprint and checksum; changing `W` or `cut` changes the fingerprint.
- [ ] Raw floats never feed the digest or a stored value.

#### Scenario: identical rerun matches, W is fingerprint-affecting
- GIVEN two runs differing only in `W` (10 vs 12)
- WHEN fingerprints are computed
- THEN the fingerprints differ; two identical runs share one fingerprint.

#### Scenario: float excluded from checksum
- GIVEN raw float metrics from a completed run
- WHEN the checksum is computed
- THEN only Decimal-quantized `Numeric(20,8)` values feed the digest; raw floats never persist.

### DLE-09: Weights Persistence — Custom Format, ≤16 MiB, Validated

As the authorized, versioned exception to MLE-01 (limited to `dl/`, D2), `dl_weights` SHALL
store one BLOB per trained model in the custom format `magic + format_version + fingerprint +
tensor manifest + raw float32 + SHA-256`. Persistence SHALL use NO pickle/joblib. Size SHALL be
≤16 MiB per BLOB. On load/verify, the store MUST reject tampered bytes (SHA-256 mismatch),
fingerprint mismatch, wrong `format_version`, and oversized blobs. There SHALL be NO
public/arbitrary weight-loading surface and NO weights download endpoint; weights are
write-validated at commit and read-validated by any internal consumer (e.g. future `predict`).

**Acceptance**
- [ ] Saved BLOBs contain magic+version+fingerprint+manifest+float32+SHA-256; zero pickle/joblib bytes anywhere.
- [ ] Tampered, wrong-version, foreign-fingerprint, or >16 MiB blobs are rejected on load.

#### Scenario: valid weights committed
- GIVEN a successful MLP/LSTM training run
- WHEN the run commits
- THEN each model writes a `dl_weights` row ≤16 MiB whose SHA-256 matches its bytes and whose fingerprint equals the run's.

#### Scenario: tampered weights rejected
- GIVEN a `dl_weights` row whose bytes were modified after commit
- WHEN a consumer loads it
- THEN load fails on integrity/fingerprint validation and no weights are exposed.

#### Scenario: oversized blob rejected
- GIVEN a weight payload exceeding 16 MiB
- WHEN the store validates it
- THEN commit fails cleanly; no snapshot payload (`active`) is written.

### DLE-10: Data Floor — ≥100 Real Draws

Training SHALL require ≥100 real draws for the lottery (D4). Below the floor, the run SHALL
end with a clean `INSUFFICIENT_DATA` result, SHALL NOT persist a snapshot, and SHALL NOT persist
weights. Synthetic fixtures SHALL be used ONLY for structural/E2E tests, never presented as real
training data.

**Acceptance**
- [ ] 10-draw fixture ⇒ `INSUFFICIENT_DATA`, zero `dl_*` rows written.
- [ ] ≥100 real draws ⇒ training proceeds; fixtures exercise both happy path and floor path.

#### Scenario: floor refusal, no snapshot
- GIVEN a lottery with 10 real draws
- WHEN training is requested
- THEN the run returns a clean `INSUFFICIENT_DATA` error and no snapshot or weights are written.

#### Scenario: floor met
- GIVEN a lottery with 120 real draws
- WHEN training is requested
- THEN the run trains and commits a `dl_*` snapshot.

### DLE-11: Registry & Scope `model_set="core-3"` + `future-dl`

The registry SHALL dispatch on `model_set`: `core-3` registers the 2 executed families (MLP,
LSTM); `future-dl` registers Transformer and TensorFlow variants as declared-but-not-executed
(MLE-07 precedent) — versioned, never scheduled. Family-name → builder is dict dispatch, no DAG;
an unknown family MUST fail fast at registration (D7).

**Acceptance**
- [ ] `core-3` executes exactly MLP + LSTM; `future-dl` produces no rows.
- [ ] Unknown family rejected with the known families listed.

#### Scenario: core-3 executes; future-dl stays declared
- GIVEN the registry is loaded
- WHEN a `train` for `model_set="core-3"` executes
- THEN exactly MLP and LSTM produce rows; Transformer/TensorFlow produce none.

#### Scenario: unknown family rejected
- GIVEN a registry request for an unregistered family
- WHEN it is requested
- THEN the registry fails fast listing the known families.

### DLE-12: Snapshot Lifecycle & Atomicity, Fingerprint Idempotency

`dl_snapshots` SHALL hold exactly one `active` per `(lottery_id, model_set)`; a successful run
writes the new version and retires the old active (and its weights rows) IN the same
transaction. On any failure the transaction rolls back and ONLY a terminal `failed` header is
persisted — never `active`/`partial`; `is_locked` is set on commit. A rerun whose
`input_fingerprint` matches an existing snapshot SHALL return that snapshot — no duplicate
version or weights row.

**Acceptance**
- [ ] Replace retires old active atomically; failure leaves only a `failed` header.
- [ ] Identical fingerprint rerun is idempotent (no duplicate version/weights).

#### Scenario: replace retires, failure marks failed
- GIVEN an active `dl_*` snapshot
- WHEN a new training run succeeds — or fails — and commits
- THEN on success the old row and its weights retire atomically; on failure only a terminal `failed` header exists and no payload or weights rows are written.

#### Scenario: idempotent rerun by fingerprint
- GIVEN an active snapshot and a retrain with identical inputs
- WHEN the identical run executes
- THEN the matching fingerprint returns the existing snapshot; no duplicate version or weights row is created.

### DLE-13: Provider Protocols Only

The engine SHALL read through its own `DrawHistoryProvider` and `FeatureSnapshotProvider`
Protocols (`dl/providers.py`); it MUST NOT import concrete F5 `probability_service` internals
and MUST NOT reuse F7 adapters. A missing feature snapshot SHALL resolve as
`SNAPSHOT_NOT_FOUND`, never zero-guessed.

**Acceptance**
- [ ] Engine references only `dl/` Protocols; F5/F7 concrete adapters never imported.
- [ ] Missing snapshot ⇒ `SNAPSHOT_NOT_FOUND`; no training attempted.

#### Scenario: missing snapshot signals absence
- GIVEN no active F4 feature snapshot for the requested lottery
- WHEN the training read path resolves X
- THEN it surfaces `SNAPSHOT_NOT_FOUND` and no training is attempted.

### DLE-14: No Scheduler — Manual Only; `/dl/predict` Deferred

Generation SHALL be manual (CLI `lip dl train` / API `POST /dl/train`), never during import.
Reads (`GET /dl/models`, `GET /dl/metrics`) MUST answer from stored `dl_*` and MUST NOT
precompute; a missing snapshot SHALL map to 404 `SNAPSHOT_NOT_FOUND`. `/dl/predict`, any
ranking/recommendation surface, and any hidden equivalent endpoint MUST NOT be implemented in
this change (deferred, F7 predict-prohibition parity).

**Acceptance**
- [ ] Reads answer from storage; missing snapshot ⇒ 404 with no training fired.
- [ ] No `/dl/predict` route and no ranking/weights-download surface registered.

#### Scenario: read never trains
- GIVEN a lottery with no `dl_*` snapshot
- WHEN a read targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and no training is triggered.

#### Scenario: predict surface absent
- GIVEN the API router after F8
- WHEN route discovery runs
- THEN `/dl/predict` is not registered; only `/dl/train`, `/dl/models`, `/dl/metrics` exist.

### DLE-15: Multi-Lottery

Every snapshot SHALL be scoped by `lottery_id`; lotteries train independently with their own
draws, windows, and targets.

**Acceptance**
- [ ] Two lotteries' snapshots/metrics/weights share no rows.

#### Scenario: per-lottery isolation
- GIVEN lotteries A and B with differing rules/draws
- WHEN both are trained
- THEN their `dl_*` rows share no data; each uses its own lottery's draws.

### DLE-16: Migration `0010` & Non-Destructive Rollback

Migration `0010_dl_tables` (`down_revision = "0009_ml_tables"`) SHALL add `dl_snapshots`,
`dl_metrics`, `dl_weights`; downgrade MUST drop ONLY `dl_*`. Rollback of F8 SHALL be additive:
downgrade 0010, revert the torch pin + exception comment, remove `app/dl/`, the service, and
routes — F1–F7 untouched.

**Acceptance**
- [ ] Upgrade adds `dl_*`; downgrade drops only `dl_*` (`ml_*` and all prior tables intact).
- [ ] 0010 up/down is idempotent and non-destructive in both directions.

#### Scenario: rollback is non-destructive
- GIVEN a DB with Core + all prior-engine tables including `ml_*`
- WHEN migration 0010 is downgraded
- THEN `dl_*` is dropped and Core/`ml_*`/`stat_*`/`feature_*`/`prob_*`/`graph_*` remain intact.

---

## Per-Model Contracts (DE-01..02)

All DE contracts share: per-number binary target (DLE-03), windowed input (DLE-04), fixed
`seed=0`, fixed seed ordering, same-env determinism (DLE-07), Decimal-quantized metrics
(DLE-08), weights in `dl_weights` (DLE-09), scope `core-3` (DLE-11).

### DE-01: MLP

The engine SHALL train an MLP classifier per target number over the flattened windowed input,
with an architecture fixed by registered defaults (layer sizes, activation, epochs, learning
rate) recorded in `params_json`; training SHALL be deterministic per DLE-07.

#### Scenario: MLP metrics persisted
- GIVEN a valid core-3 window
- WHEN MLP training completes
- THEN per-number metrics are persisted with a versioned `model_version`, weights BLOB, and a matching checksum.

#### Scenario: MLP same-input rerun identical
- GIVEN an identical input frame
- WHEN MLP retrains in the same environment
- THEN quantized metrics, checksum, and weights bytes are identical.

### DE-02: LSTM

The engine SHALL train an LSTM classifier per target number over the ordered window sequence
(DLE-04, oldest→newest), with architecture defaults recorded in `params_json`; hidden-state
initialization SHALL be deterministic (seed 0).

#### Scenario: LSTM metrics persisted
- GIVEN a valid core-3 window
- WHEN LSTM training completes
- THEN per-number metrics and a weights BLOB land in a single committed snapshot.

#### Scenario: LSTM deterministic replay
- GIVEN identical sequences
- WHEN LSTM trains twice in the same environment
- THEN quantized metrics and checksum are identical.

---

**Note**: New capability created at archive from change delta `fase-8-deep-learning`.
Engine requirements `DLE-01..16` + per-model contracts `DE-01..02` follow the ml-engine
skeleton (MLE/ME parity) as the exploration prescribed; new DL-specific requirements are
windowing (DLE-04), window-aware splitting (DLE-05), DL determinism (DLE-07), and authorized
weights persistence (DLE-09). API/CLI parity surface is specified in the sibling delta
`specs/backend/spec.md` (MODIFIED REQ-10/11/12).