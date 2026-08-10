# Design: Fase 8 — Deep Learning Engine

**Change**: `fase-8-deep-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Predecessors**: exploration → proposal (D1–D8) → spec (`dl-engine` DLE-01..16, DE-01..02; `backend` REQ-10/11/12 delta)

## Technical Approach

A new engine package `app/dl/` mirroring F7's `ml/` skeleton exactly (engine, registry, fingerprint, determinism, splitter, providers, snapshot_store, version) plus three DL-only modules (window builder, sequence builder, weights store). Pure engine stays DB-free; `DlService` is the composition root owning one atomic transaction per run. F7's `ml/` is imported **nowhere** in `dl/` — every row type, quantizer, and Protocol is re-declared locally (DLE-13 isolation, zero coupling to frozen F7). Deps: `torch` CPU exact-pinned with a signed transitive-`networkx` exception limited to the torch F8 tree (DLE-06, proposal D1). Model targets run-scoped `core-3` (MLP + LSTM executed; Transformer/TensorFlow declared `future-dl`).

## Architecture Decisions

| # | Decision | Alternatives | Rationale |
|---|---|---|---|
| D-A1 | **One `dl_snapshots` row per run** (both families), 2 `dl_weights` rows + 2×N `dl_metrics` rows under it | F7's per-family snapshot | DLE-11/12 require one active per `(lottery_id, model_set)` and DE-02 "single committed snapshot"; avoids F7's multi-family active ambiguity |
| D-A2 | `dl/` 100% self-contained; duplicate `quantize_metric`/`compute_metrics_checksum` (~15 LOC) in `dl/determinism.py` | Import from `ml/determinism.py` | DLE-13 "Provider Protocols only" + F7 frozen; zero-risk isolation, parity marked by comment |
| D-A3 | Weights persisted as one SQLite BLOB per family (custom format, DLE-09); **write**-validate at commit, **read**-validate on load | Filesystem; pickle | SQLite = project precedent (no FS path policy); custom format excludes pickle/joblib wholly |
| D-A4 | Fingerprint is **run-scoped**: `{data_hash, hyperparameters{mlp,lstm}, architecture{mlp,lstm}, seed, window, cut, DL_GENERATOR_VERSION}` | Per-family fingerprint | One snapshot/run ⇒ one fingerprint key for DLE-12 idempotency; weights embed the run fingerprint (DLE-09) |
| D-A5 | `W` recorded in `dl_snapshots.window` header column (like `cut`) | Params-only | `W` is fingerprint-affecting (DLE-04/08); header is the immutable run record |
| D-A6 | Eval-only metrics: metrics computed **only** on eval windows | Train+eval | DLE-05 scenario; `roc_auc` chance baseline when eval split is single-class (F7 parity) |
| D-A7 | `INSUFFICIENT_DATA` = new `ServiceError` code → envelope 422; `LeakageError` mapped to `ValidationError` (422) | 400; 500 | Clean result below floor (DLE-10, never 500); leakage is a client-visible invalid split (DLE-05) |
| D-A8 | Base metric set per number: `accuracy, precision, recall, f1, roc_auc` | BCE loss only | F12 comparability with F7 (`ml_metrics` cell contract) |

## Data Flow

    CLI lip dl train ─┐
    POST /dl/train ───┤→ DlService.train(lottery_id, model_set, window, cut)   ← ONE atomic tx
                      │    1. count draws < 100 ⇒ INSUFFICIENT_DATA (no rows)
                      │    2. active F4 snapshot? None ⇒ SNAPSHOT_NOT_FOUND
                      │    3. WindowBuilder(Draws+Features, W) → frames n∈[W, N-1]
                      │    4. WindowSplitter(frames, cut, W) → train ∪ eval, gap dropped
                      │    5. DlEngine.train: per family ⇒
                      │         SequenceBuilder → tensors (float32) → MLP|LSTM(n=...)
                      │         metrics quantize(20,8) → checksum; state_dict → weights BLOB
                      │    6. create_snapshot(active) → bulk metrics+weights → retire_old
                      │       → commit; failure ⇒ rollback + terminal failed header
                      └→ dl_snapshots + dl_metrics + dl_weights (only dl_* touched, DLE-02)

    GET /dl/models|metrics → DlStore reads active snapshot only; 404 SNAPSHOT_NOT_FOUND; never trains.

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/pyproject.toml` | Modify | Exact-pin `torch==2.5.1` (CPU wheel) + signed networkx-transitive exception comment (D1) |
| `backend/tests/test_ml_pr1.py` (ban-gate) | Modify | Extend scan to `app/dl/`; torch pin asserted; networkx still absent from installable deps |
| `backend/src/backend/app/models/dl_snapshot.py`, `dl_metric.py`, `dl_weight.py` | Create | Header + normalized metric + weights entity (below) |
| `backend/src/backend/app/models/__init__.py` | Modify | Register the 3 entities (alembic target_metadata) |
| `backend/alembic/versions/0010_dl_tables.py` | Create | `down_revision="0009_ml_tables"`; creates 3 tables + 3 indexes; downgrade drops only `dl_*` (DLE-16) |
| `backend/src/backend/app/dl/{__init__,registry,fingerprint,determinism,version,window,splitter,sequence_builder,engine,snapshot_store,weights,providers}.py` | Create | Pure engine package (below) |
| `backend/src/backend/app/services/dl_service.py` | Create | Composition root, atomic lifecycle, `find_by_fingerprint` idempotency (DLE-12) |
| `backend/src/backend/app/api/v1/dl.py` + `router.py` | Create/Modify | 3 routes (+ adapters `_DrawAdapter`/`_FeatureAdapter`); mount router |
| `backend/src/backend/app/schemas/dl.py` | Create | TrainRequest/ModelsList/MetricsRead (design-time parity, avoids F7 schema drift) |
| `backend/src/backend/app/cli.py` | Modify | `lip dl train|models|metrics` (+ `_CliDrawAdapter`/`_CliFeatureAdapter`) |
| `backend/src/backend/app/services/errors.py` | Modify | Add `InsufficientDataError("INSUFFICIENT_DATA")` |
| `backend/tests/dl/*`, `tests/test_dl_pr1.py` | Create | Unit/integration/e2e suites + PR1 dependency-gate |
| `API_SPECIFICATION.md` §9, README, PROJECT_STATUS, `openspec/specs` | Modify | `/dl/predict` removed from delivered surface; docs-drift reconciliation |

**`app/dl/` modules and public API**

| Module | Responsibility | Public API |
|---|---|---|
| `registry.py` | Dict-dispatch; `MODEL_SET_CORE_3`, `FUTURE_DL_FAMILIES=("transformer","tensorflow")` | `build_dl_registry()` → immutable `{slug: (builder, defaults)}`; unknown family fails fast (DLE-11) |
| `fingerprint.py` | Canonical SHA-256, `sort_keys=True` | `compute_dl_fingerprint(data_hash, hyperparams, architecture, seed, window, cut, DL_GENERATOR_VERSION)` |
| `determinism.py` | Seed 0, `torch.manual_seed(0)`, `use_deterministic_algorithms(True)`, `set_num_threads(1)`, float32; local quantize/checksum | `configure_deterministic_torch()`, `quantize_metric`, `compute_metrics_checksum` (DLE-07/08) |
| `version.py` | `DL_GENERATOR_VERSION = "1.0.0"` | constant |
| `providers.py` | Protocols: `DrawHistoryProvider.iter_draws(lottery_id)` → `DrawRow(draw_number, numbers)`; `FeatureSnapshotProvider.active_snapshot_id` / `feature_rows` → `FeatureRow(feature_id, draw_number, value)`; absence ⇒ `None`, never zero-guessed (DLE-13) | Protocols + frozen dataclasses |
| `window.py` | `WindowBuilder`: `W` consecutive F4 vectors per frame `n`, ordered `n-W+1..n`; validation error if `W` (2..20) > draws−1; missing draws ⇒ `SnapshotNotFoundError`; no padding (DLE-04) | `build_windows(draws, rows, W)` → `list[Window]` |
| `splitter.py` | Window-aware walk-forward: train windows end ≤ cut, eval windows start > cut; gap dropped; `LeakageError` on straddle/interleave/shuffle (DLE-05) | `split_windows(windows, cut)`, `validate_windows(train, eval, cut)` |
| `sequence_builder.py` | windows + per-number `y` (n+1 participation) → numpy matrices → `torch.float32` tensors (oldest→newest, canonical order); no shuffle | `build_tensors(windows, draws)`, DL feature order = F7's `ML_FEATURE_ORDER` (F12) |
| `engine.py` | `DlEngine.train(family, lottery_id, records, feature_rows, W, cut)` → `TrainResult{family, metrics, quantized, models: {number: nn.Module}, fingerprint, checksum, train_draws, eval_draws}` | pure engine, DB-free |
| `snapshot_store.py` | `DlSnapshotStore`: `get_active`, `find_by_fingerprint`, `next_version`, `create_snapshot`, `retire_old_active`, `mark_failed`, `bulk_insert_metrics`, `bulk_insert_weights`, `weights_for_snapshot` — lifecycle enforcement lives here (MLE-08 parity) | read/write owner |
| `weights.py` | Custom format serialize/validate (below); ≤16 MiB; no pickle/joblib (DLE-09) | `encode_weights(state_dict, fingerprint, model_id, model_version)` → bytes; `validate_weights(blob, fingerprint)` |

**MLP (DE-01)**: per number — flatten `W×F` (100) → `Linear(100,64)` → `ReLU` → `Linear(64,1)` `BCEWithLogitsLoss`, `Adam(lr=1e-3)`, 50 epochs, batch 32.
**LSTM (DE-02)**: per number — `LSTM(input=F, hidden=64, num_layers=1, batch_first=True)`; last hidden → `Linear(64,1)`; `BCEWithLogitsLoss`, `Adam(lr=1e-3)`, 50 epochs, batch 32; hidden init seeded (seed 0). Walk-forward eval: per number per eval window `(accuracy, precision, recall, f1, roc_auc)`, aggregating per draw-row as F7 does per row.

## Interfaces / Contracts

**Weights format (dl/weights.py)** — zero pickle/joblib bytes:

    magic "LIPDLW01" (8B) | format_version u32=1 | fingerprint 64B ascii |
    manifest_len u32 | manifest (canonical JSON: model_id, model_version, tensor_count, dtype="float32", shapes) |
    per tensor: name_len u32+name | ndim u32+dims | raw float32 LE |
    sha256 32B over all preceding bytes

Validation (write and read): magic, `format_version==1`, fingerprint matches run, `len ≤ 16 MiB`, `sha256` recompute-equal; state keys sorted, non-float params rejected. `params_json`/`dl_metrics` never carry state bytes (DLE-01).

**Schemas** — `dl_snapshots`(id PK, lottery_id FK→lottery RESTRICT, model_set, version, dl_generator_version, checksum, input_fingerprint, cut, window, status, is_locked, draw_count, draws_from, draws_to, created_at, updated_at; UNIQUE(lottery_id,model_set,version); CHECK range, CHECK status∈active|retired|failed); `dl_metrics`(id PK, snapshot_id FK RESTRICT, model_id, model_version, number, metric_name, value Numeric(20,8), params_json; UNIQUE(snapshot_id,model_id,number,metric_name)); `dl_weights`(id PK, snapshot_id FK RESTRICT, model_id, model_version, format_version, size_bytes, sha256, weights BLOB; UNIQUE(snapshot_id,model_id); CHECK size_bytes≤16777216). Indexes: `(lottery_id,model_set,status)`, `(snapshot_id,model_id)`×2. Migration `0010` additive; downgrade drops only `dl_*` (non-destructive, DLE-16 scenario).

**API** — `POST /dl/train` (params: lottery_id, model_set="core-3", window=None, cut=None): 200 `SuccessEnvelope`; 404 `RESOURCE_NOT_FOUND`/`SNAPSHOT_NOT_FOUND`; 422 `INSUFFICIENT_DATA`/`validation_error` (bad W, leakage). `GET /dl/models` → registry (executed + future-dl) + active snapshot or 404. `GET /dl/metrics?model_id=` → stored metrics or 404. No `/dl/predict`, no weights download (DLE-14). **CLI**: `lip dl train --lottery <code> [--window 10] [--cut N] [--model-set core-3]`, `lip dl models|metrics --lottery <code> [--model mlp]`; JSON output (F7 parity), same floor/leakage behavior.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | WindowBuilder (default W, W=1/25 rejected, history < W clean error, missing draw); splitter (straddle/shuffle ⇒ `LeakageError` RED, clean split, gap dropped); sequence tensors (shape/order/dtype/float32); weights (round-trip, tamper/W signature/fingerprint/size reject); fingerprint (`W`/`cut` change ⇒ digest change); determinism (non-deterministic op fails run, no active snapshot); floor (<100 ⇒ `INSUFFICIENT_DATA`, zero rows) | `tests/dl/test_window.py`, `test_splitter.py`, `test_sequence.py`, `test_weights.py`, `test_fingerprint.py`, `test_determinism.py`, `test_floor.py` |
| Integration | Store lifecycle (atomic replace retires old + weights, failure ⇒ only `failed` header, `find_by_fingerprint` idempotent); migration 0010 up/down non-destructive (`ml_*` intact); API 3 routes (404/422 maps, no predict route); CLI parity; ban-gate (`app/dl/` no networkx/banned imports, torch pin) | `tests/dl/test_snapshot_store.py`, `test_migration.py` (via conftest fixtures), `test_api.py`, `test_cli.py`, `tests/test_dl_pr1.py` |
| E2E | GF1: two seeded CPU runs on identical synthetic 120-draw fixtures ⇒ identical fingerprint + checksum + quantized metric rows + weights bytes; anti-leakage end-to-end (straddle run writes nothing); weights live only in `dl_weights` BLOB (parse object store) | `tests/dl/test_dl_determinism_e2e.py` (120-draw synthetic fixture, structural/E2E only, DLE-10) |

## Threat Matrix

N/A — this change adds API routes and CLI argument parsing but no routing/shell-command/subprocess/VCS/PR-automation/executable-classification/process-integration boundary. The CLI builds FastAPI/queries, never shells out; the weights BLOB is validated by magic/version/SHA-256 before any read (security handled in `weights.py` tests above).

## Migration / Rollout

`0010_dl_tables` (down_revision `0009_ml_tables`): upgrade adds `dl_snapshots`/`dl_metrics`/`dl_weights` + 3 indexes; downgrade drops only `dl_*` (Core + `ml_*`/`stat_*`/`feature_*`/`prob_*`/`graph_*` intact). Rollback: downgrade 0010, revert torch pin + exception comment, remove `app/dl/`, service, routes — F1–F7 untouched. No data migration (new schema only). Torch landed with its signed networkx exception before `app/dl/` imports it (PR order below).

## PR Breakdown (stacked to main, each ≤400 LOC)

| PR | Files (groups) | Est. LOC | Depends on |
|---|---|---|---|
| PR1 | pyproject pin + ban-gate + `0010_dl_tables` + 3 models | ~240 | — |
| PR2 | `dl/` registry · fingerprint · determinism · version + PR1 tests | ~380 | PR1 |
| PR3 | `dl/` window · splitter · sequence_builder | ~360 | PR2 |
| PR4 | `dl/` engine (MLP/LSTM) · weights + training tests | ~380 | PR3 |
| PR5 | `dl_service.py` · `api/v1/dl.py` · schemas · CLI + integration tests | ~330 | PR4 |
| PR6 | E2E determinism + anti-leakage e2e + docs (API_SPEC §9, README, PROJECT_STATUS) | ~350 | PR5 |

## Open Questions

- [ ] Exact torch CPU version resolved at apply (proposal D1: stable 2.x; pin `torch==2.5.1` unless apply-time resolution finds a better stable).
- [ ] `INSUFFICIENT_DATA` HTTP status: 422 chosen (validation-family); confirm at review if 400 preferred.