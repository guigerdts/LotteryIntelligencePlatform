# Exploration — Fase 8: Deep Learning

**Change**: `fase-8-deep-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Artifact**: exploration (pre-proposal) · **Type**: architecture

---

## 1. Dependencies and Policy Conflicts

### Findings

- `backend/pyproject.toml` (lines 21–29) carries a **signed allowlist exception**:
  `scikit-learn==1.6.1` + `numpy==2.2.6` exact-pinned are "the ONLY permitted runtime
  dep for `ml/`" (proposal D1, design M-A9), registered 2026-08-09. The comment states
  `xgboost/lightgbm/catboost/networkx` **remain BANNED** (`future-ml` declared-but-
  never-executed, MLE-07).
- The ban is enforced by `tests/test_ml_pr1.py::test_no_future_ml_imports`: scans
  `ml/` module import surfaces for the 4 banned names AND greps the `pyproject.toml`
  installable-deps list. `uv.lock` currently contains **zero** torch/tensorflow
  references; the venv has only numpy 2.2.6 + sklearn 1.6.1.
- `openspec/config.yaml` context (init-time, 2026-08-06): "ML with
  Scikit-Learn/XGBoost/LightGBM/CatBoost; **DL with PyTorch**". README "Tecnologías":
  "Deep Learning — **PyTorch**, TensorFlow (opcional)".
- `requires-python = ">=3.12"`; actual venv is Python 3.13 (openspec config) — torch
  CPU wheels exist for both.
- **Torch transitive dependency conflict**: `torch` hard-depends on `networkx`,
  `sympy`, `jinja2`, `filelock`, `fsspec`, `typing-extensions` (2.x metadata). The F6
  gate (graph D8: "networkx/numpy/scipy banned", tasks.md line 292) and F7 ban-gate
  policy name `networkx` as banned. The pyproject grep test checks only *installable*
  deps, so a transitive `networkx` would NOT trip the test — but it would de-facto
  violate the documented "networkx banned" policy statement.

### Implications

- Fase 8 requires a **second signed dependency exception** (D1 precedent): PyTorch
  (documented choice) with an exact-pin policy and the TCP/IP wheel/CI footprint the
  project has never carried (F0–F7 were stdlib + sklearn only).
- The existing naming-based ban test does not block torch, so a new `dl/` package
  would pass it unchanged; the *policy* (allowlist exception + pinning + ban-gate
  coverage) must be re-signed, and the torch→networkx transitive relationship needs
  an explicit acceptance or a policy re-scope.
- TensorFlow is documented as "opcional" — a `future-dl` declared-never-executed
  entry (MLE-07 precedent) can absorb it.

### Open Questions

1. PyTorch only (documented), or PyTorch + TensorFlow optional?
2. CPU-only wheels or GPU-capable? (CUDA wheels are multi-GB; portability/CI cost.)
3. Accept torch's transitive `networkx`/`sympy` deps as a documented exception, or
   re-scope the "networkx banned" policy statement?
4. Exact-pinning policy for torch and its transitive tree (uv.lock currently clean).

---

## 2. Available Data / Features (Fases 3–7)

### Findings

- **F4 features (X)**: `app/ml/features.py` — `ML_FEATURE_ORDER` = the 10 base F4
  feature ids in canonical sorted order (consecutive_count, current_frequency,
  decade_distribution, draw_mean, draw_range, draw_sum, low_high_ratio,
  max_current_gap, odd_even_ratio, repeated_from_previous), pinned as an immutable
  10-tuple by `test_ml_pr1.py::test_ml_feature_order_frozen`. Persisted per draw in
  `feature_values (snapshot_id, feature_id, draw_number, value)`; active snapshot
  resolved by `FeatureSnapshotProvider.active_snapshot_id`.
- **Statistics (F3)**: `stat_snapshots` + `stat_frequency`, `stat_frequency_position`,
  `stat_gap`, `stat_average`, `stat_scalar` (only `entropy` scalar exists). F3 pending
  slices — distributions, trends, correlations — are **not implemented**; trend/
  distribution/correlation-derived features are unavailable (F7 exploration §2).
- **Graph (F6)**: `graph_snapshots` + `graph_values` — co-occurrence, degree/closeness/
  betweenness centrality, communities, density, modularity — cells
  `(metric_type, subject, draw_number)` with `value Numeric(20,8)`.
- **Probability (F5)**: `prob_snapshots` + `prob_values` — hypergeometric, empirical
  rates, MC aggregates/quantiles, Bayes, conditional — cells `(model, version,
  subject, draw_number)`.
- **ML (F7)**: `ml_snapshots` (header, `model_set="core-5"`, `cut`, fingerprint,
  checksum) + `ml_metrics (model_id, number, metric_name, value Numeric(20,8),
  params_json)`.
- **Data volume reality**: the only importable fixture is `baloto_draws.json` =
  **10 draws**. The live `database/lip.db` has lottery L1 (min 1, max 50, selects 6)
  with **0 draws, 0 datasets, 0 snapshots of every engine type** (only a `stat_snapshots`
  count of 1 row observed, no payloads). Real Baloto/Revancha histories are on the
  order of thousands of draws (Baloto since 2001) — **not verified in this repo**;
  no real CSV is present.

### Implications

- DL can reuse the exact same per-draw `X` (F4 vector at `n`), and may stack stat/
  graph/prob scalars per draw — but F7's implemented `providers.py` exposes ONLY
  `DrawHistoryProvider` + `FeatureSnapshotProvider` (the designed `StatSnapshotReader`
  was dropped in implementation); a DL engine wanting stat/graph/prob inputs must
  define its own reader Protocols.
- **Data scarcity is the dominant constraint**: 10-draw fixture can neither train nor
  meaningfully eval MLP/LSTM/Transformers. DL tests need either large synthetic
  fixtures or a documented minimum-draws floor; the live DB cannot train anything yet.
- The F3-pending features gap means sequence-based DL features (raw number windows,
  embedding tables) may be the only non-F4 signal without implementing F3 slices.

### Open Questions

1. Minimum draw count below which DL refuses to train (clean error, MLE-12 precedent)?
2. Do DL inputs = frozen F4 vector, F4 + stat/graph/prob scalars, or DL-specific
   sequences (raw numbers / feature windows)?
3. Biggest synthetic fixture an e2e determinism test (GF1 pattern) can afford on CPU?

---

## 3. Reusable Patterns (Fase 7 ML Engine)

### Findings

- **Package layout**: `app/ml/` (pure engine: `engine.py`, `registry.py`,
  `fingerprint.py`, `determinism.py`, `splitter.py`, `providers.py`, `feature_reader.py`,
  `snapshot_store.py`, `features.py`, `version.py`) + `services/ml_service.py`
  (composition root) + `api/v1/ml.py` + CLI. `dl/` already exists as a scaffold
  (`dl/__init__.py` docstring: "Deep-learning model engines (Fases 7-8)"); `ml/__init__.py`
  is "Classical machine learning model engines (Fases 7-8)". README "Seams de paquetes"
  and SYSTEM_ARCHITECTURE tree list `ml/` and `dl/` as separate packages from Fase 0.
- **Atomic lifecycle** (MLE-08): `create_snapshot(active)` → `bulk_insert_metrics` →
  `retire_old_active` → one commit; failure → rollback + terminal `failed` header,
  never `active/partial`. `is_locked` on commit. One active per `(lottery_id, model_set)`.
- **Registry** (MLE-07/M-A2): dict-dispatch `build_ml_registry()`; `model_set="core-5"`
  executes 5 sklearn families; `FUTURE_ML_FAMILIES` = xgboost/lightgbm/catboost
  declared-but-never-scheduled; immutable `MappingProxyType`.
- **Fingerprint** (MLE-05): canonical SHA-256 over `{data_hash, params (JSON-
  serializable hyperparams only), ML_GENERATOR_VERSION, cut}` — `sort_keys=True`.
- **Determinism** (MLE-05/D2/D4): `quantize_metric` → Decimal(20,8) BEFORE any
  checksum; `get_deterministic_state(seed)` seeds numpy; same-env-only claim; GF1
  two-DB E2E (`tests/ml/test_ml_determinism_e2e.py`) asserts byte-identical
  fingerprint + checksum + metric rows.
- **Walk-forward** (MLE-03): `walk_forward_split(records, cut)` → `train ≤ cut < eval`;
  `validate_split(strict)` raises `LeakageError`; anti-shuffle RED test.
- **Provider Protocols only** (MLE-06): engine imports only `DrawHistoryProvider` /
  `FeatureSnapshotProvider`; adapters duplicated at composition root per surface
  (`_DrawAdapter`/`_FeatureAdapter` in `api/v1/ml.py`, `_CliDrawAdapter`/
  `_CliFeatureAdapter` in `cli.py`) — 2× duplication is the established pattern.
- **Surface**: `POST /ml/train` (query params `lottery_id`, `family`) + `GET /ml/models`
  + `GET /ml/metrics`; CLI `lip ml train|models|metrics`; reads never precompute,
  404 `SNAPSHOT_NOT_FOUND`; envelope.
- **Design drift noted**: design.md promised `schemas/ml.py` (TrainRequest/MlModelsList/
  MetricsRead) and `scope="incremental"` idempotency via `find_by_fingerprint`; the
  implemented API/CLI use raw query params and the service always writes a new version
  (no scope parameter; `find_by_fingerprint` exists in the store but is not called).

### Implications

- A parallel `dl/` package mirroring every module is the lowest-friction path: engine,
  registry, fingerprint, determinism, splitter, providers, snapshot_store, version,
  service, api, cli. Pure helpers (quantize, canonical JSON digest, walk-forward)
  could be shared as stateless imports without violating Protocol isolation (MLE-06
  bans concrete `probability_service` reuse, not stateless utils) — a design decision.
- `MlSnapshotStore`/`ml_*` schema is a ready template for `dl_*` (header + normalized
  metrics payload + `params_json`).
- The `future-ml` declared-never-executed mechanism maps directly onto
  `future-dl` (e.g., TensorFlow variants declared, never scheduled).

### Open Questions

1. New `dl/` package with duplicated helpers vs shared imports of `ml/` pure modules?
2. One snapshot per DL family (F7 pattern) vs one snapshot per run with per-model
   rows?
3. Reuse `ml/splitter.py` semantics for windowed sequences, or a new window-aware
   splitter (see §5)?

---

## 4. Technical Risks and Determinism

### Findings

- F7 determinism holds a **same-env byte-identical gate** (GF1, two seeded DBs) via
  `random_state=0`, fixed feature order, numpy seeding, and quantize-before-checksum.
  sklearn is deterministic on CPU.
- **PyTorch non-determinism is documented, not hypothetical**: `cudnn.benchmark`,
  atomicAdd accumulation, autograd scheduling, multi-thread reduction order.
  `torch.use_deterministic_algorithms(True)` exists (CPU and some CUDA ops) but
  rejects some ops and slows training; GPU float sums are non-associative.
- **Weights ban is a hard contract**: MLE-01 scenario "weights never persisted"
  asserts no joblib/pickle bytes in any column/table; design.md explicitly rejected
  "persisting weights/joblib blobs (MLE-01)". F7's `TrainResult.models` holds fitted
  classifiers in memory and **discards them after metrics** — acceptable for sklearn
  (seconds), but a DL training run (minutes–hours, epochs/backprop) thrown away after
  metrics is economically questionable. DL weights CANNOT be reconstructed from
  hyperparameters — the state_dict IS the model.
- No GPU evidence anywhere (config/env/venv CPU-only).
- `torch.save`/`pickle`-family loading of untrusted state dicts is a security surface;
  SQLite BLOB vs filesystem storage both have no precedent in this repo.
- Determinism E2E seeding: `test_ml_determinism_e2e.py` seeds a feature set whose
  names differ from `ML_FEATURE_ORDER` (test-internal drift) — relevant when F8 builds
  its own determinism E2E.

### Implications

- The GF1 byte-identical gate is at risk for DL training. Most likely bounded
  contract: CPU-only + `use_deterministic_algorithms(True)` + fixed seeds + single
  threading + quantized-metrics checksum — but this must be a **new decision**, not
  assumed to port from sklearn.
- The **weights persistence question is the central architectural conflict** of F8:
  metrics-only (wasteful, contract-consistent) vs persisted weights (new storage +
  policy + rollback semantics + security).
- Training time pushes DL toward CLI-first (manual-only MLE-09 already) and away from
  synchronous API calls without a timeout/background strategy.

### Open Questions

1. Bounded determinism contract for DL (CPU deterministic algorithms, same-env) vs
   relaxed quantized-metrics-only gate — and does the GF1 two-DB E2E still apply?
2. Persist weights (dl_weights table / filesystem) or discard after metrics?
3. GPU in scope for F8, or CPU-only explicitly?
4. API synchronous training semantics (request timeout/background job) or CLI-only
   training?

---

## 5. Target and Temporal Strategy

### Findings

- F7 target (D3): `y` = binary per-number participation in draw `n+1`; one model per
  `(family × number)`, `X` = F4 vector at `n`. Frame rows `n ∈ [1, N-1]`; last draw has
  no target. Walk-forward `train ≤ cut < eval`, `cut` default `len(frame)*4//5`,
  participates in fingerprint.
- No `/ml/predict`, no ranking (F7 "Out": predict-in-production excluded).
- The `draw_number` axis is the strict temporal ordering everywhere
  (`ORDER BY draw_number, id`).
- LSTM/Transformers need **sequences**: windows of `W` consecutive draws ending at
  `n` → predict `n+1`. No windowing exists anywhere yet.

### Implications

- Keeping the same binary per-number target preserves **cross-phase comparability**
  (F12 Meta Learning evaluates all models against the same objective — README
  "cada algoritmo competirá utilizando métricas objetivas").
- Window length `W` becomes a fingerprint-affecting hyperparameter (like `cut`).
  Windowed splits create a NEW leak surface: a train window ending at `n ≤ cut` is
  fine, but windows must never straddle `cut` (eval-window start must be `> cut`);
  the existing `walk_forward_split`/`validate_split` reason about rows, not windows —
  a separate or extended validator is needed.

### Open Questions

1. Same binary per-number target as F7 (recommended-for-comparability) vs new target
   (multi-class next-draw, probability/ranking output)?
2. Sequence definition: number embeddings per position, F4 feature-vector windows, or
   F4 + scalars per position? `W` default and bounds?
3. Window-aware anti-leakage validator contract (extension of MLE-03 or new requirer)?

---

## 6. Persistence / API / CLI Impact

### Findings

- Migration chain is strictly additive: `0005_stat` → `0006_feature` → `0007_prob` →
  `0008_graph` → `0009_ml` (down_rev chain; 0009 downgrade drops ONLY `ml_*`, MLE-10).
  Next head would be `0010_dl_tables` with `down_revision="0009_ml_tables"`.
- `ml_snapshots` header template: `lottery_id FK RESTRICT, model_set, version,
  ml_generator_version, checksum, input_fingerprint, cut, status, is_locked,
  draw_count, draws_from, draws_to, created_at, updated_at` + Unique(lottery_id,
  model_set, version) + CHECKs. `ml_metrics` payload: `(snapshot_id, model_id,
  model_version, number, metric_name, value Numeric(20,8), params_json)`.
- API_SPECIFICATION §9 documents `/dl/models`, `/dl/train`, **`/dl/predict`**.
  F7 deliberately excluded `/ml/predict` + `/ml/ranking` (proposal "Out"). CLI
  precedent: `lip ml train|models|metrics`.
- No weights storage exists anywhere; `params_json` is hyperparameters-only.

### Implications

- Following the pattern, F8 implies `dl_snapshots` + `dl_metrics` (+ `dl_weights` only
  if weights are authorized) via `0010_dl_tables`, additive downgrade dropping only
  `dl_*` — exact MLE-10 mirror.
- `/dl/*` router + `lip dl train|models|metrics` parity is the F7 template. `model_set`
  would carry the DL scope (e.g., `core-3` = mlp/lstm/transformer), one snapshot per
  family (F7) or one per run.
- **`/dl/predict` tension**: API_SPEC §9 lists it; F7's "no predict-in-production"
  principle would push it out of scope; docs-vs-delivered drift must be resolved by
  the proposal (same class of drift the F7 proposal already reconciled for `/ml/*`).

### Open Questions

1. Separate `dl_*` tables (pattern-consistent) — confirmed, or reuse `ml_*`
   (would violate the "dedicated schema" spirit of MLE-01)?
2. `dl_weights` persistence + storage medium (SQLite BLOB vs filesystem referenced
   from header) + size policy?
3. API surface: new `/dl/*` router (documented) vs extending `/ml/*`?
4. `/dl/predict` in scope or deferred (F7 precedent)?
5. CLI: `lip dl train|models|metrics` only, or also predict/export?

---

## 7. Compatibility with Existing Restrictions

### Findings

- **Float red line (MLE-05/D4)**: metrics quantize to Decimal `Numeric(20,8)` before
  checksum/persist; float never enters a fingerprint/checksum/stored value. Ports
  directly to `dl_metrics`.
- **No weights (MLE-01)**: "no serialized model bytes in any column or table" —
  written for `ml_*`; `dl_*` tables are new, but the philosophy (metrics-only engine)
  is F7's founding rationale. DL is the first engine where this restriction is
  costly and possibly wrong.
- **Provider Protocol isolation (MLE-06)**: engines import only their own Protocols;
  never the F5 `probability_service` adapter (latent `models.stat_value` bug). DL
  must define/use its own providers.
- **Manual-only (MLE-09)**: manual train, reads never precompute, 404 on missing.
- **Additive migration (MLE-10)**: 0009 downgrade drops only `ml_*` — 0010 mirrors.
- **Allowlist (MLE-04/D1/M-A9)**: sklearn+numpy only for `ml/`; F8 extends with torch
  and re-surfaces the **networkx transitive conflict** (F6 D8 ban-gate names
  `networkx`; torch pulls it transitively).

### Implications

- The Decimal quantize pipeline, atomic lifecycle, manual-only surface, and additive
  migration all port cleanly.
- The **two genuinely conflicting contracts** are (a) weights-persistence ban and
  (b) the networkx-banned dependency policy (transitive conflict). Both need explicit
  authorization; neither blocks the other.
- Determinism gate grade (G1-style byte-identical vs bounded) is a third compatibility
  question, softer than the other two (F7 itself already bounded it to same-env).

### Open Questions

1. Extend the no-weights ban to `dl_*`, or lift it with a signed exception for DL
   (with storage/rollback/security policy)?
2. Is torch's transitive `networkx` acceptable under a re-scoped policy statement?
3. Does the GF1 same-env byte-identical E2E requirement apply to DL training, or a
   weaker quantized-metrics equality?

---

## 8. Conflicts with Previous Phase Decisions / Contracts

### Findings

- **F7 banned names** are exactly `xgboost, lightgbm, catboost, networkx` (proposal D1,
  MLE-07, M-A9). `torch` is NOT in that list — no direct name conflict; the
  transitive-networkx issue is the real collision.
- **F7 "Out" scope** explicitly excluded "weights/DL/optimization/generator" —
  F8 is the roadmap's designated successor, consistent (IMPLEMENTATION_ROADMAP Fase 8:
  MLP, LSTM, Transformers; dependency chain ML → DL → Optimization).
- **`ML_FEATURE_ORDER` frozen** (M-A5 + contract test) — frozen for the `ml/` engine;
  a `dl/` engine is free to define its own input contract (or reuse the same order,
  which maximizes F12 comparability).
- **Registry precedent**: `core-5` executes / `future-ml` declared. DL families map
  exactly onto this: `core-3` executed with `future-dl` declared variants
  (e.g., TensorFlow).
- **Spec structure**: F7 created a NEW capability `ml-engine` (MLE-01..12 + ME-01..05)
  with a MODIFIED backend REQ-10/11/12 delta. F8 follows the same additive path: new
  `dl-engine` capability + backend delta. Note: `ml-engine` and `graph-engine` specs
  are NOT yet merged into `openspec/specs/` (archive pending for F6/F7), so both
  existing-change folders are the precedent to read, and the F8 deltas will land on
  a spec tree that still lacks ml-engine content.
- **Documented intent conflicts**: API_SPEC §9 lists `/dl/predict` (and §8
  `/ml/ranking`, already deferred by F7); README model lists mention Naive Bayes (F7
  declined) and "Deep Learning: PyTorch, TensorFlow (opcional)"; roadmap Fase 8 =
  exactly MLP/LSTM/Transformers. Recurring docs-drift pattern, resolved per-phase in
  proposals (F7 precedent).

### Implications

- F8 is architecturally a **new engine capability parallel to `ml/`**, not an
  extension of ml-engine; every F7 contract stays frozen and untouched.
- The two contract collisions needing sign-off are weights-persistence and the
  torch/networkx dependency policy (§7). Everything else ports cleanly.
- The future-declared registry mechanism gives F8 a ready-made home for
  declared-but-never-executed DL variants.

### Open Questions

1. New capability `dl-engine` (DLE-xx + per-model DE-xx) vs extending `ml-engine`
   (MLE-xx)? (Severity: the additive-spec system supports both; new capability is the
   zero-risk path.)
2. Does `core-3` (MLP/LSTM/Transformer) all execute, or does minimum-viable-F8
   execute fewer and declare the rest `future-dl`?
3. `/dl/predict`: documented in API_SPEC §9, deferred by F7's predict-prohibition —
   in scope for F8 or not?

---

## 9. Product/Scope Decisions Requiring Authorization

Findings and implications above surface the following authorization points (no
recommendation made here — decisions belong to the proposal):

1. **Framework**: PyTorch only vs PyTorch + TensorFlow-optional; CPU-only vs GPU;
   exact-pin + transitive-dep acceptance (incl. `networkx` policy re-scope).
2. **Weights persistence**: metrics-only (F7 philosophy) vs authorized `dl_weights`
   storage (medium, size policy, rollback, security).
3. **Determinism grade**: GF1 same-env byte-identical (CPU deterministic algorithms)
   vs quantized-metrics-only equality for DL training.
4. **Data floor**: minimum draw count (10-draw fixture is unusable for DL); synthetic
   fixture strategy for tests; real-data import expectation.
5. **Target**: binary per-number participation in n+1 (comparability) vs new target.
6. **Inputs**: frozen F4 vector, F4+stat/graph/prob scalars, or DL sequences
   (windowed features / raw numbers; `W` in fingerprint).
7. **Surface**: `/dl/train`, `/dl/models`, `/dl/metrics`; `/dl/predict` in/out;
   `lip dl ...` parity.
8. **Schema**: `dl_snapshots` + `dl_metrics` (+`dl_weights`), migration `0010`,
   additive downgrade; separate `dl_*` vs shared `ml_*`.
9. **Scope**: all three models (MLP/LSTM/Transformer) executed vs minimum-viable
   subset with the rest declared `future-dl`; where the DL registry lives
   (`ml/` vs `dl/`) and `model_set` naming.
10. **Spec shape**: new `dl-engine` capability (DLE/DE requirement IDs) + backend
    delta (MODIFIED REQ-10/11/12 pattern).

---

## Evidence Map

| Claim | Evidence |
|---|---|
| Allowlist exception + pin | `backend/pyproject.toml` lines 21–29; `tests/test_ml_pr1.py::test_no_future_ml_imports` |
| Banned names | proposal D1; design M-A9; `ml/registry.py` `FUTURE_ML_FAMILIES` |
| ML_FEATURE_ORDER frozen | `ml/features.py`; `test_ml_pr1.py::test_ml_feature_order_frozen` |
| Atomic lifecycle | `ml/snapshot_store.py`, `services/ml_service.py`, MLE-08 |
| Fingerprint/determinism | `ml/fingerprint.py`, `ml/determinism.py`, `ml/version.py` |
| Walk-forward anti-leak | `ml/splitter.py`; MLE-03 |
| Provider Protocols | `ml/providers.py`; MLE-06 |
| Weights ban | MLE-01 scenario; design.md "Rejected: persisting weights/joblib blobs" |
| Data availability | F7 exploration §2; live `database/lip.db` (0 draws); `baloto_draws.json` (10) |
| Docs intent (PyTorch, /dl/*) | README Tecnologías; API_SPEC §9; ENGINE_SPEC §10; SYSTEM_ARCHITECTURE tree; openspec/config.yaml |
| Roadmap Fase 8 | IMPLEMENTATION_ROADMAP.md (MLP, LSTM, Transformers; dep chain) |
| F7 closed, specs unmerged | `openspec/changes/fase-7-machine-learning/archive-report.md`; `openspec/specs/` lacks ml-engine |
| Design drift (schemas/ml.py, scope) | design.md §Module Map vs implemented `api/v1/ml.py` + `cli.py` |

## Next Step

**`sdd-propose`** — the proposal must obtain user authorization on §9 (framework,
weights, determinism grade, data floor, target, inputs, surface, schema, scope,
spec shape) and record the torch→networkx transitive conflict and the empty-data
state of the live DB.