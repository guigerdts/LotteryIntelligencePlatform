# Tasks: Fase 7 — Machine Learning Engine

**Change**: fase-7-machine-learning · **Store**: openspec · **Date**: 2026-08-09
**Artifact**: tasks (this change) — implementation tasks.

## Overview

Deterministic, metrics-only ML training per lottery: 5 scikit-learn families (RF, Extra Trees, Gradient Boosting, SVM, KNN) under `model_set="core-5"`; `X` = F4 features at draw `n` in fixed `ML_FEATURE_ORDER`, `y` = binary per-number participation in draw `n+1`; walk-forward split (`train ≤ cut < eval`) with anti-shuffle rejection. Own Provider Protocols only (never F5 `probability_service`), canonical SHA-256 fingerprint over data+params+`ML_GENERATOR_VERSION`, Decimal(20,8)-quantized metrics before checksum/persist, `ml_*` snapshots with atomic lifecycle, migration `0009_ml_tables` (prob/graph-safe rollback), manual CLI+API only, no weights, no `/ml/predict`. Scikit-learn is the sole new dep (allowlist exception). Stacked-to-main: PR1..PR6, each ≤400 LOC.

## Review Workload Forecast

```text
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium
```

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2,110 (range 2,000–2,200; 6 stacked PRs) |
| 400-line budget risk | Medium — PR3/PR4/PR5 sit at 380–400; split overflow into the chain before merging |
| Chained PRs recommended | Yes — 6 slices, each ≤400 (chain pre-authorised by locked decisions) |
| Chain strategy | stacked-to-main (each PR merges to main in order) |
| Delivery strategy | ask-on-risk — orchestrator asks before apply |
| Decision needed before apply | Yes — ask-on-risk; chain strategy already locked to stacked-to-main |

## PR Plan (Dependency Graph)

```
PR1 (deps+models+0009) → PR2 (package+registry+fingerprint+determinism)
  → PR3 (walk-forward+engine) → PR4 (store+service) → PR5 (API+CLI) → PR6 (e2e+docs)
```

| PR | Scope | Est. LOC | Depends on |
|----|-------|----------|------------|
| PR1 | pyproject pin + `ml_snapshot`/`ml_metric` ORM + migration 0009 + migration/dep-gate tests | 230 | None |
| PR2 | `ml/` package seam, `ML_FEATURE_ORDER`, providers, registry (core-5 + future-ml), fingerprint, determinism + tests | 380 | PR1 |
| PR3 | walk_forward split + leakage RED test + engine (frame/fit/metrics/quantize) + engine fixtures | 390 | PR2 |
| PR4 | snapshot_store lifecycle + MlService + adapters + service/store tests | 400 | PR3 |
| PR5 | `schemas/ml.py` + API router `/ml/*` + CLI `lip ml …` + API/CLI tests | 390 | PR4 |
| PR6 | determinism e2e + backend parity + docs + final gates | 300 | PR5 |

## Tasks

### PR1 — Foundation: deps, schema, migration (≈230 LOC)

| ID | Ph. | Description | Files touched | Acceptance | Est. LOC |
|----|-----|-------------|---------------|-----------|---------|
| T-01 [x] | design | Pin `scikit-learn>=1.4,<2` + `numpy` in `backend/pyproject.toml` (allowlist exception to F6 stdlib gate, D1); keep `xgboost/lightgbm/catboost/networkx` absent from installable deps | `backend/pyproject.toml`, `backend/uv.lock` | `uv lock` resolves; allowlist-test asserts the 4 future-ml names absent from installable deps | 15 |
| T-02 [x] | impl | Create `models/ml_snapshot.py` + `models/ml_metric.py` — header fields (`ml_snapshots` table) + normalized payload (`ml_metrics`: `value Numeric(20,8)`, `params_json` hyperparameters only, never weights); `Unique(lottery_id, model_set, version)`, `status CHECK active|retired|failed`; register both in `models/__init__.py` for `Base.metadata` | `backend/src/backend/app/models/ml_snapshot.py`, `models/ml_metric.py`, `models/__init__.py` | ORM maps; FK `lottery_id` RESTRICT; checks/unique per design | 120 |
| T-03 [x] | design | Create `0009_ml_tables.py` — upgrade creates `ml_snapshots` + `ml_metrics` + indexes (`lottery_id, model_set, status`; `snapshot_id, model_id`); `down_revision="0008_graph_tables"`; downgrade drops ONLY `ml_*` | `backend/alembic/versions/0009_ml_tables.py` | `alembic upgrade head` then `downgrade -1` leaves Core/stat_*/feature_*/prob_*/graph_* intact | 80 |
| T-04 [x] | test | 0009 rows exercised in `tests/test_migrations.py` (HEAD_TABLES_0009 assert swaps) + `tests/test_ml_pr1.py` (`test_upgrade_creates_ml_tables` / `test_downgrade_drops_only_ml_tables`); upgrade adds `ml_*`, downgrade drops only `ml_*`, prior tables intact | `backend/tests/test_migrations.py`, `tests/test_ml_pr1.py` | 2 tests green (non-destructive rollback, additive) | 40 |
| T-05 [x] | test/gate | Dep gate in `tests/test_ml_pr1.py` (`test_no_future_ml_imports`) — scikit-learn present in installable deps; `xgboost/lightgbm/catboost/networkx` absent; run `pytest tests/test_migrations.py tests/test_ml_pr1.py` + ruff | `backend/tests/test_ml_pr1.py` | Gate passes; PR1 ruff+pytest green | 25 |

### PR2 — Package seam, registry, determinism (≈380)

> PR2 apply (orchestrator re-scope): registry builder + fingerprint + determinism +
> walk-forward splitter delivered; PR2 tests consolidated in `backend/tests/test_ml_pr2.py`.
> T-07 providers deferred to the PR3 engine slice — the splitter (T-09) was pulled forward.

| ID | Ph. | Description | Files touched | Acceptance | Est. LOC |
|----|-----|-------------|---------------|-----------|---------|
| T-06 [x] | design | `ml/__init__.py` — keep docstring seam; `ml/version.py` — `ML_GENERATOR_VERSION: str = "1.0.0"` (pulled into PR1 by apply scope; version constant lives in `version.py` per the docstring-only seam rule, not `__init__.py`); `ml/features.py` — `ML_FEATURE_ORDER` frozen tuple with exactly the 10 canonical F4 core ids (M-A5 order); the order is part of the fingerprint contract | `backend/src/backend/app/ml/__init__.py`, `ml/version.py`, `ml/features.py` | No logic beyond version/order; test asserts tuple equality + independence from other engines' constants | 20 |
| T-07 | impl | `ml/providers.py` — `DrawReader`, `FeatureSnapshotReader`, `StatSnapshotReader` Protocols + `DrawRow`/`LotteryRules`/`FeatureVector` carries; `ORDER BY draw_number, id`; missing ⇒ `None`, never guessed | `backend/src/backend/app/ml/providers.py` | Protocol-only file: zero concrete imports; contract test (T-10) passes | 60 |
| T-08 [x] | impl | `ml/registry.py` — `FamilyDefinition`-style dict-dispatch; core-5 executes (rf/et/gb/svm/knn, `random_state=0` where supported); future-3 `FUTURE_ML_FAMILIES` (xgboost/lightgbm/catboost) declared, never built; `build_ml_registry()` returns slug→(class, params); unknown family ⇒ fails listing known ids | `backend/src/backend/app/ml/registry.py` | Registry returns exactly 5 built + 3 declared; seed policy stable; no DAG | 70 |
| T-09 [x] | impl | `ml/fingerprint.py` + `ml/determinism.py` + `ml/splitter.py` — canonical JSON `sort_keys=True` → SHA-256; `quantize_metric()` → Decimal `Numeric(20,8)`; `compute_metrics_checksum()` digests ONLY quantized values; `walk_forward_split(records, cut)` temporal split (train `< cut`, eval `== cut`, ValueError out-of-range, no shuffle) | `backend/src/backend/app/ml/fingerprint.py`, `ml/determinism.py`, `ml/splitter.py` | `tests/test_ml_pr2.py`: equal inputs ⇒ identical hex; key order irrelevant; quantized-only checksum; split deterministic | 90 |
| T-10 | test | `tests/ml/test_registry_isolation.py` — core-5 executes 5, future-ml declared 3 with ZERO rows after a run; unknown family fails listing known; `tests/ml/test_providers.py` — protocol contract, no concrete seam; module-var scan: `ml/` + service never import `xgboost|lightgbm|catboost|networkx` | `tests/ml/test_registry_isolation.py`, `tests/ml/test_providers.py` | isolation + seam tests green; banned-import scan clean | 140 |

### PR3 — Walk-forward + Engine (≈390)

| ID | Ph. | Description | Files touched | Acceptance | Est. LOC |
|----|-----|-------------|---------------|-----------|---------|
| T-11 [x] | test (RED) | Consolidated into `tests/test_ml_pr3.py` (`test_anti_shuffle_rejected`, `test_engine_walk_forward_respects_cut`) — interleaved eval-before-cut asserts `LeakageError` with zero writes; walk-forward asserts train/eval disjoint; no `tests/ml/` dir (PR1-3 tests flat) | `backend/tests/test_ml_pr3.py` | RED-first delivered as splitter GREEN tests in `test_ml_pr3.py` | 70 |
| T-12 [x] | impl | `ml/splitter.py` (delivered with PR2 slice, T-09) — `walk_forward_split(records, cut)` → (train ≤ cut, eval > cut); `validate_split(strict)` raises `LeakageError` on any eval row ≤ cut; empty-side cut ⇒ ValueError | `backend/src/backend/app/ml/splitter.py` | PR3 suite green: subsets proper; shuffled → leakage, nothing written; ruff | 50 |
| T-13 [x] | impl | `ml/engine.py` — pure train: build X per n from active F4 rows in `ML_FEATURE_ORDER` (via `feature_reader.build_feature_matrix`); y per number k = 1 iff in draw n+1; fit core-5 `random_state=0` (KNN deterministic); metrics `accuracy, precision, recall, f1, roc_auc` quantized to Decimal(20,8) before checksum; missing snapshot ⇒ `SNAPSHOT_NOT_FOUND` before fitting | `backend/src/backend/app/ml/engine.py`, `ml/feature_reader.py` | PR3 suite green: per-number targets, fixed column order, Decimal in every value | 110 |
| T-14 [x] | test | `tests/test_ml_pr3.py` (flat layout; `tests/ml/` not used) — engine fixtures: train basic + determinism, canonical feature order, quantized-only metrics, no-future-models, walk-forward cut, anti-shuffle, `SNAPSHOT_NOT_FOUND` | `backend/tests/test_ml_pr3.py` | GREEN: all 8 fixtures pass; rerun determinism asserted; 19 tests green with PR2 suite | 120 |

### PR4 — Store + Service (≈400)

| ID | Ph. | Description | Files touched | Acceptance | Est. LOC |
|----|-----|-------------|---------------|-----------|---------|
| T-15 | impl | `ml/snapshot_store.py` — get_active, find_by_fingerprint, next_version, create(header, locked), ordered bulk-insert values, retire_old_active, mark_failed; single `ml_*` I/O owner | `backend/src/backend/app/ml/snapshot_store.py` | store tests (T-16) green | 100 |
| T-16 | test | `tests/ml/test_snapshot_store.py` — lifecycle atomicity: new version + retire old in ONE tx; failure ⇒ terminal `failed` header only, zero payload rows, `is_locked` on commit; writes confined to `ml_*` | `backend/tests/ml/test_snapshot_store.py` | atomic replace / fail-only tests green; read-only gate byte-identical | 90 |
| T-17 | impl | `services/ml_service.py` — private adapters over `DrawRepository`, `FeatureEngineService.read_features`/`FeatureValueRepository`, `StatisticsService.get_active` (never `probability_service`); resolve → fingerprint → split → train → atomic persist → `failed` on error; idempotent `scope="incremental"`; reads serve stored rows only, 404 `SNAPSHOT_NOT_FOUND`, never precompute | `backend/src/backend/app/services/ml_service.py` | service scenarios (T-18) green | 140 |
| T-18 | test | `tests/ml/test_ml_service.py` — deterministic rerun, idempotent incremental (same fingerprint ⇒ existing version, no duplicate), replace-retire atomic, `SNAPSHOT_NOT_FOUND` on missing, empty-draws clean `ValidationError` (MLE-12), read-only writes gate, no `probability_service` import | `backend/tests/ml/test_ml_service.py` | service suite green incl. NOT_FOUND + empty-DB fixtures | 130 |

### PR5 — API + CLI (≈390)

| ID | Ph. | Description | Files touched | Acceptance | Est. LOC |
|----|-----|-------------|---------------|-----------|---------|
| T-19 | impl | `schemas/ml.py` — `TrainRequest(lottery_code/id, model_set, cut)`, `MlModelsList`, `MetricsRead` (envelope reuse); `api/v1/ml.py` — `POST /ml/train` (201/200 idempotent), `GET /ml/models`, `GET /ml/metrics`; mount in `api/v1/router.py`; missing ⇒ 404 `SNAPSHOT_NOT_FOUND`; reads never precompute | `backend/src/backend/app/schemas/ml.py`, `api/v1/ml.py`, `api/v1/router.py` | API tests (T-20) green | 60 |
| T-20 | test | `tests/api/test_ml_api.py` — train 201/200 + read 404, leakage-invalid train rejected, `/statistics/generate` still 200 (parity baseline), read never triggers train | `backend/tests/api/test_ml_api.py` | 5 scenarios green incl. parity baseline | 95 |
| T-21 | impl | `cli.py` — `lip ml train|models|metrics` mirroring API (same `lottery/model_set/cut` options; argparse only, no scheduler/import hook) | `backend/src/backend/app/cli.py` | CLI/API parity: reads print stored snapshot data | 25 |
| T-22 | test | `tests/api/test_ml_cli.py` — subprocess CLI trains snapshot and prints models/metrics; reads never train | `backend/tests/api/test_ml_cli.py` | CLI parity e2e green | 70 |

### PR6 — E2E + Docs + Gates (≈300)

| ID | Ph. | Description | Files touched | Acceptance | Est. LOC |
|----|-----|-------------|---------------|-----------|---------|
| T-23 | test | `tests/ml/test_ml_determinism_e2e.py` — two identical seeded DBs (CLI+API paths): same inputs ⇒ identical quantized fingerprint + checksum + metric rows (same-env, GF1) | `backend/tests/ml/test_ml_determinism_e2e.py` | both DBs byte-identical after full run | 100 |
| T-24 | test | `tests/ml/test_ml_backend_parity.py` — untouched `POST /statistics/generate` returns 200 on F3 fixture; `POST /ml/train` additive-only; stats surface unchanged (REQ-10/11/12 scenarios intact) | `backend/tests/ml/test_ml_backend_parity.py` | parity green; additive diff proven | 90 |
| T-25 | docs | Refresh README + PROJECT_STATUS + IMPLEMENTATION_ROADMAP — ML section, `/ml/*` + `lip ml` examples, core-5/future-ml isolation note, scikit-only allowlist note | `README.md`, `PROJECT_STATUS.md`, `IMPLEMENTATION_ROADMAP.md` | docs list ML surface; Fase 7 marked per roadmap | 90 |
| T-26 | gate | Final gates: full pytest suite, `ruff check` clean, migration up/down non-destructive, per-PR ≤400 LOC recorded | none | gates green; records kept | 20 |

## Mandatory Gates

- **Byte-determinism rerun**: T-14 unit + T-23 e2e — identical quantized metrics/checksum on replay
- **Anti-shuffle RED**: T-11 — shuffled split raises `LeakageError`, zero rows written; walk-forward train/eval never intersect
- **Lifecycle atomicity**: T-16 — replace = retire-in-tx; failure ⇒ terminal `failed` only, no partial rows; `is_locked` on commit
- **`SNAPSHOT_NOT_FOUND`**: T-18 unit + T-20 API 404 — never precompute (MLE-09)
- **Allowlist/ban-gate**: T-05 (pyproject deny 4 names) + T-10 (5 executed + 3 declared; banned-import scan; no `probability_service` adapter)
- **Backend parity**: T-20/T-24 — `POST /statistics/generate` still 200; additive surface only
- **Per-PR gate**: `backend/.venv/bin/pytest <PR-files> -q && backend/.venv/bin/ruff check backend/src -q` before merging each slice

## Risks & Notes

- PR3/PR4/PR5 at 380–400 LOC: watch budget; split T-13 or T-17/T-19 into an extra stacked PR before review if running over (chain absorbs).
- `ML_FEATURE_ORDER` must match F4 catalog ids EXACTLY (M-A5) — order participates in fingerprint; a different `cut` always yields a new version.
- No weights/joblib anywhere; `params_json` holds frozen hyperparameters only (MLE-01 scenario "weights never persisted").
