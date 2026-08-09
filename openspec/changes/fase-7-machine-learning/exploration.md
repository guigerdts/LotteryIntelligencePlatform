# Exploration — Fase 7: Machine Learning

**Change**: `fase-7-machine-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Artifact**: exploration (pre-proposal) · **Type**: architecture

---

## 1. Current State

The codebase implements five completed engine phases (F0 Foundation, F1 Core Domain,
F2 Data/Import, F3 Statistics, F4 Feature, F5 Probability) plus a completed-but-unarchived
F6 Graph Engine (`openspec/changes/fase-6-graph-engine/` — only `tasks.md` + empty `specs/`
present; graph code is committed and green). Every engine follows ONE established pattern:

### 1.1 The versioned-snapshot engine pattern (F3→F6 parity)

- A domain package owns the pure algorithms + registry + snapshot store:
  - `statistics/` (`engine.py`, `generator.py`, `checksum.py`)
  - `feature_engineering/` (`engine.py`, `registry.py`, `fingerprint.py`, `providers.py`, `features/`)
  - `probability/` (`engine.py`, `registry.py`, `fingerprint.py`, `determinism.py`, `providers.py`, `snapshot_store.py`)
  - `graph/` (`cooccurrence.py`, `construction.py`, `centrality.py`, `community.py`, `metrics.py`, `engine.py`, `snapshot_store.py`)
- A domain service class at the composition root (`services/statistics_service.py`,
  `services/feature_engine_service.py`, `services/probability_service.py`,
  `services/graph_service.py`) that: resolves the lottery (`lottery_code` | `lottery_id`),
  computes the deterministic payload, computes the `input_fingerprint` (SHA-256 over
  canonical compact JSON — `sort_keys=True, separators=(",",":")`), computes the output
  `checksum`, then persists header + values in ONE atomic transaction
  (`create_snapshot` → `bulk_insert_values` → `retire_old_active` → `commit`).
- On any failure: `rollback` + persist a terminal `failed` header (dead metadata only,
  never `active`/`partial`, never reused).
- Idempotency: `scope="incremental"` returns the existing `active` snapshot when its
  fingerprint/checksum matches (`find_by_fingerprint` / `find_by_checksum_version`);
  `scope="full"` always writes a NEW version and retires the old `active`.
- Snapshot headers (`stat_snapshots`, `feature_snapshots`, `prob_snapshots`,
  `graph_snapshots`) carry: `id, lottery_id, {scope_key}, version, {engine}_generator_version,
  checksum, input_fingerprint, status('active'|'retired'|'failed' CHECK), is_locked,
  draw_count, draws_from, draws_to, created_at, updated_at`. Unique
  `(lottery_id, {scope_key}, version)`; scope keys: `metric_set`, `feature_set`,
  `model_set`, `graph_type`.
- Payload rows (`stat_*` families, `feature_values`, `prob_values`, `graph_values`) are
  normalized, keyed on the **`draw_number` axis with NO physical FK to `draw`**, exact
  `Decimal` (Numeric(20,8)) values, and a per-row `params_json` (graph/prob) or composite
  PK (feature/stat).
- **Version constants** pinned per engine: `STATS_GENERATOR_VERSION`, `FEATURE_GENERATOR_VERSION`,
  `PROB_GENERATOR_VERSION`, graph `version="1.0.0"` — bumped ONLY when algorithm/params
  change persisted output. An ML engine needs an `ML_GENERATOR_VERSION`.
- **Provider Protocols only** (PES-06 / FES-06 / A9): engines import ONLY `Protocol`
  seams (`DrawProvider`, `StatsSnapshotRef`, `StatisticsProvider`, `DatasetProvider`,
  `DrawReader`, `StatSnapshotReader`, `FeatureSnapshotReader`), never concrete repo/model
  internals. Adapters live at the composition root in the service.

### 1.2 Registries and determinism

- `FeatureRegistry` — declarative `FeatureDefinition` + Kahn topo sort + fail-fast cycle
  detection; **`future-statistics` sourced features are declared + versioned but NEVER
  scheduled** (FES-08 / GF2(b), proven by `tests/test_registry_isolation.py`).
- `ProbMethodRegistry` — dict-dispatch of 7 method `MethodDefinition`s (D-A2) — ML models
  fit this simpler pattern (independent models, no DAG).
- Determinism: `feature_input_fingerprint` / `probability_input_fingerprint` /
  `stat_checksum` — canonical order-independent JSON; Monte Carlo uses
  `derive_seed` + `isolated_rng(random.Random(seed))`; float NEVER enters fingerprint,
  checksum, or persisted values. The GF1 test pattern
  (`tests/test_determinism.py`) runs TWO independent, identically-seeded tmp DBs and
  asserts byte-identical header + payload + insertion order + content hash, then repeats
  it through the CLI and API surfaces.

### 1.3 API and CLI parity (REQ-10/11/12 + per-engine P*-08)

- `api/v1/` routers: strict write/read separation — `POST /{engine}/generate|compute` is
  the ONLY write path and is idempotent; `GET` routes read ONLY persisted snapshots and
  NEVER precompute (404 `SNAPSHOT_NOT_FOUND` when missing). Fase 0 envelope
  (`SuccessEnvelope`). Routers only parse + delegate; no SQL/business logic.
- `cli.py` (`lip` console script): per-engine subcommands with `generate|rebuild|compute|list|show`.
- Requirement IDs: statistics `STE-01..13`, feature `FES-01..`, probability `PES-01..11` +
  `PM-01..07`, graph `GES-*/REQ-*`, chained into `openspec/specs/backend/spec.md` REQ-10/11/12.
- Example spec for the ML delta: `openspec/specs/probability-engine/spec.md` (engine-level
  requirements with Given/When/Then scenarios — the F7 spec will mirror `MLE-..`/`ME-..`).

---

## 2. Data Available for Training

All read paths are read-only `Session`-scoped; ML can consume the existing snapshots
through Provider Protocols, exactly as Probability does today.

| Source | Paths | Shape available today |
|---|---|---|
| Lottery rules | `models/lottery.py` | `min_number, max_number, numbers_to_select, super_number_*` per lottery |
| Raw draws | `models/draw.py`, `models/draw_number.py`; `repositories/draw_repository.py` | `draw_number`, `draw_date`, numbers per position, `jackpot`, `winners`; `iter_draws(..., after_draw_number=)` batched keyset; NO `is_deleted` filter leak (soft-deleted excluded in repo) |
| Dataset composition | `models/dataset.py`, `models/dataset_draw.py` | versioned, immutable, checksummed dataset header + composition join (declared but NOT yet exercised as a provider seam — `DatasetProvider` Protocol exists in `feature_engineering/providers.py`) |
| Statistics snapshot | `stat_snapshots` + `stat_frequency`, `stat_frequency_position`, `stat_gap`, `stat_scalar` (`entropy`) | per-number counts, per-position counts, gap summaries, NULL-aware jackpot/winners means, entropy scalar |
| Feature snapshot | `feature_snapshots` + `feature_values` | **per-draw feature vectors** keyed `(feature_id, draw_number)` — 10 core features (sum, mean, range, odd/even, low/high, consecutives, decades, repeats, max gap, frequency) = the natural row-level X per draw |
| Probability snapshot | `prob_snapshots` + `prob_values` | per-method per-subject rows (hypergeometric, empirical rates, MC aggregates/quantiles, Bayes, conditional) |
| Graph snapshot | `graph_snapshots` + `graph_values` | co-occurrence, degree/closeness/betweenness centrality, communities, density, modularity |

### Forward training target: the `draw_number` axis

Feature values are per-draw (`(snapshot_id, feature_id, draw_number)`) — a supervised
frame is X = feature vector at draw `n`, y = outcome at draw `n+1` (or per-number
present/absent in the next draw). All existing payloads join strictly on the logical
`draw_number`; strict temporal ordering (`ORDER BY draw_number, id`) is a hard
requirement mirrored everywhere.

### Blockers / pending neighbors (document, DO NOT implement)

- Fase 3 pending slices: **distributions, trends, entropy, correlations** are declared
  in `IMPLEMENTATION_ROADMAP.md` (F3 "Pendiente para slices futuros") and NOT present as
  features (only `entropy` in `stat_scalar`). Trend / distribution / correlation-derived
  features are therefore unavailable to train on — must be declared-but-skipped
  (`future-statistics` pattern) or excluded.
- Fase 5 latent defect discovered during exploration:
  `services/probability_service.py` `_StatsReaderAdapter.frequencies()` imports
  **`backend.app.models.stat_value` which DOES NOT EXIST** on disk or in git history
  (verified: `ModuleNotFoundError` on direct import; no test references it; F5 suite
  passes because the member is lazily imported only when an active stat snapshot
  exists). Any F7 consumer that reads frequencies through that adapter will crash;
  F7 must not reuse that path and the defect should be tracked for a F5 patch.

---

## 3. Dependency Policy — THE open decision

- Every prior engine phase is **stdlib-only**. Fase 6 gate checklist explicitly:
  **"networkx/numpy/scipy banned"** (graph `tasks.md`), and `pyproject.toml`
  dependencies contain NO ML library (fastapi, sqlalchemy, alembic, pydantic,
  pydantic-settings, uvicorn, httpx, pytest, python-multipart, ruff; optional
  `dialect-pg` only).
- The roadmap's model list (8: Random Forest, XGBoost, LightGBM, CatBoost, Extra Trees,
  Gradient Boosting, SVM, KNN) is NOT satisfiable in pure stdlib in anything realistic —
  tree ensembles, gradient boosting, and SVM require float matrix math.
- README (tech stack) + `API_SPECIFICATION.md §8` (`GET /ml/models`, `POST /ml/train`,
  `POST /ml/predict`, `GET /ml/metrics`, `GET /ml/ranking`) document Scikit-Learn /
  XGBoost / LightGBM / CatBoost as the intended ML surface. The docs CONFLICT with the
  established stdlib-only runtime discipline — this must be resolved by proposal.

Coverage without any new dep split:

| Roadmap model | sklearn | xgboost | lightgbm | catboost | stdlib-only |
|---|---|---|---|---|---|
| Random Forest | ✓ RandomForestClassifier | – | – | – | ✗ |
| XGBoost | – | ✓ `xgboost` | – | – | ✗ |
| LightGBM | – | – | ✓ `lightgbm` | – | ✗ |
| CatBoost | – | – | – | ✓ `catboost` | ✗ |
| Extra Trees | ✓ ExtraTrees | – | – | – | ✗ |
| Gradient Boosting | ✓ GradientBoosting | ✓ | ✓ | – | ✗ |
| SVM | ✓ SVC | – | – | – | ✗ |
| KNN | ✓ KNN | – | – | – | (painful) |

Note: README lists **9** models (adds Naive Bayes) while IMPLEMENTATION_ROADMAP.md lists
**8** — a documented inconsistency the proposal must reconcile.

---

## 4. Approaches

| # | Approach | Pros | Cons | Effort |
|---|----------|------|------|--------|
| A | **Stdlib-only** (hand-rolled KNN/Naive-Bayes/logistic; no new deps) | Zero dependency risk; keeps the Fase 6 "banned libs" gate intact | Cannot deliver the roadmap's 8 model families honestly; huge implementation surface; weak predictive power; goes against README's documented intent | High |
| B | **scikit-learn only** (5 of the 8 families: RF/ET/GB/SVM/KNN; XGBoost/LightGBM/CatBoost declared "future"-versioned but never scheduled) | ONE well-maintained dep; covers the testable majority; mirrors the `future-statistics` declared-never-scheduled precedent (FES-08); keeps xgboost/catboost risk out; sklearn is the first lib named in README's intended stack | 3 roadmap models deferred — phase "Resultado: pipeline de entrenamiento" is 5/8 executed; still requires relaxing the Fase-6 ban (numpy/sklearn) | Medium |
| C | **Full stack** (sklearn + xgboost + lightgbm + catboost) | Roadmap-consistent; richest engine | 4 new deps; large footprint; native/compiled deps complicate the portable-DDL/CI story; cross-env byte determinism of boosting libs is hard to own; documents intent vs reality | High |

### Recommendation

**B — scikit-learn only, with the remaining 3 families declared `future-scheduled`**
(registered, versioned, never executed in F7 — the FES-08 "declared, never computed"
precedent). This keeps the deterministic snapshot contract feasible (sklearn models with
`random_state=0` are — in practice — the most reproducible of the options), gives the
training pipeline a realistic majority of the roadmap's families, prescripts the F6
stdlib-only precedent with a single, documented exception, and leaves XGBoost/LightGBM/
CatBoost to F8+ (they are listed alongside sklearn in README's stack, so the dep policy
needs the user's sign-off regardless).

---

## 5. Affected Areas

- `backend/pyproject.toml` — new dependency (sklearn / numpy) chosen in proposal
- `backend/alembic/versions/0009_ml_tables.py` — new migration (head `0008_graph_tables`)
- `backend/src/backend/app/models/ml_snapshot.py` + `ml_value.py` (or `ml_metric.py`)
  + `models/__init__.py` registration (ALEMBIC target metadata)
- `backend/src/backend/app/ml/` — engine package (mirrors `probability/`):
  `registry.py` (model definition + build registry), `models.py` (pure learner wrappers
  respecting a common Protocol + engine immutability), `fingerprint.py`,
  `determinism.py` (fixed `random_state`, isolated RNG), `metrics.py` (classification
  metrics + baseline), `providers.py` (Protocol: DrawReader + stat/feature/graph reader),
  `snapshot_store.py` (ml_* lifecycle)
- `backend/src/backend/app/services/ml_service.py` — composition root: adapters, atomic
  tx, `failed` header, fingerprint/checksum, scope
- `backend/src/backend/app/api/v1/ml.py` + `router.py` mount; `schemas/ml.py`
- `backend/src/backend/app/cli.py` — `lip ml train|models|metrics` parity
- `backend/tests/ml/…`, `backend/tests/test_ml_determinism.py`, `backend/tests/test_migrations.py`
  (0009 up/down), plus reuse of `backend/tests/fixtures/baloto_draws.json`
- `openspec/specs/ml-engine/spec.md` (engine spec), `README.md` + `PROJECT_STATUS.md`

---

## 6. Risks

1. **Dependency policy conflict** — F6 gate banned numpy/scipy/networkx; F7's model list
   (RF, XGB, LGBM, CB, ET, GB, SVM, KNN) cannot be delivered stdlib-only. Needs explicit
   user decision in proposal/design (Option B recommended).
2. **Determinism contract vs the strict byte-identical gate** — all prior engines hold a
   G1/G9-style gate: two independent runs on identical datasets produce identical bytes.
   ML trained models can't be compared byte-for-byte across environments on 1-arch
   differences in BLAS/thread accumulation. Must define a new, bounded determinism
   contract (fixed `random_state` + fixed feature order + fixed seed + same-env
   byte-identical runs; model *evaluation metrics* checksummed via canonical quantization).
3. **float-vs-Decimal persistence** — every payload table today is `Numeric(20,8)` Decimal,
   "float NEVER reaches a persisted value". Model scores/accuracy are floats; decide how to
   persist them deterministically (fixed precision Decimal quantization) without breaking
   the old invariant.
4. **Training data / leakage control** — no target can be defined without deciding the
   intent (predict next-draw numbers? class of next occurrence per number?). Strict
   temporal ordering (`ORDER BY draw_number`) + walk-forward / no-look-ahead split
   MUST be tested; naive random split = leakage (contradicts CHARTER restriccioes
   "separar claramente entrenamiento, validación y evaluación").
5. **Tradeoff: model scope** — 8 vs 9 models (README adds Naive Bayes) is inconsistent;
   also F7 only promises "pipeline de entrenamiento", while API_SPECIFICATION.md lists
   `/ml/train`, `/ml/predict`, `/ml/metrics`, `/ml/ranking`. Proposal must decide which
   surfaces land in F7 (recommend train + metrics only; peer predict/ranking/export to
   later F₈/F10).
6. **Fase 3 pending slices** (distributions/trends/entropy/correlations) would enrich
   features but are not implemented — feature set for ML is limited to what F34 provides
   today; declare as skipped, don't implement here.
7. **Latent F5 defect** — `probability_service` imports missing `models/stat_value`; a
   live ML consumer reading stat frequencies through that adapter crashes.
8. **PR/commit budget** — F6 was delivered as 8 numerical PRs (PR1a→PR7, each ≤ 400 LOC).
   A full ML train path + metrics + tests is bigger; forecast chained PRs per
   build unit: migration → models → engine+registry → snapshot store → service → API+CLI
   → fixtures+determinism e2e. 400-line budget guard is active.

---

## 7. Decisions the proposal MUST resolve (key_decision_draft)

1. **Dependency policy**: stdlib-only vs scikit-learn-only (recommended) vs full stack —
   and the fate of the F6 "networkx/numpy/scipy banned" gate.
2. **Model scope**: which of the roadmap's alternatives to implement now (B: 5 executed,
   3 declared-future) vs deliver; and reconcile 8 vs 9 (Naive Bayes).
3. **Training target definition**: what y is (per-number binary / multi-class next-draw),
   plus the split scheme (temporal walk-forward, no-look-ahead) that protects the given
   CHARTER restriction on leakage.
4. **Determinism contract**: the byte-identical G1-gate vs a new "same-env, seeded,
   quantized-metrics" contract; where float is allowed and at what precision.
5. **Snapshot contract**: header shape (`ml_snapshots` scope key — `model_set`), payload
   (metrics + per-model artifacts as JSON vs no weights), `ML_GENERATOR_VERSION` policy.
6. **API/CLI surface for F7**: full API_SPEC §8 (`/ml/models`+`/ml/train`+`/ml/metrics`
   +`/ml/predict`+rank) or a trimmed "training + metrics" parity; CLI parity.

---

## 8. Next step

**`sdd-propose`** — the proposal must let the user pick a dependency policy (options
A/B/C, recommend B) and must record the F3-slice + F5-defect findings. The engine spec
after the proposal should follow the `probability-engine` spec skeleton
(`openspec/specs/probability-engine/spec.md`) with engine reqs `MLE-01..` and the
determinism test plan mirrors `tests/test_determinism.py`.