# Design: Fase 7 — Machine Learning Engine

## Context & Goals

Deterministic, metrics-only ML training for each lottery: 5 scikit-learn families (Random Forest, Extra Trees, Gradient Boosting, SVM, KNN) under scope `model_set="core-5"`; `X` = F4 per-draw feature vector (fixed canonical order) at draw `n`, `y` = binary per-number participation in draw `n+1`. Walk-forward split (`train ≤ cut < eval`) blocks leakage; XGBoost/LightGBM/CatBoost are `future-ml` declared-but-never-executed. Result: immutable `ml_*` snapshots (F3–F6 contract), manual-only lifecycle, same-env determinism with Decimal-quantized metrics, atomic single-transaction writes. No weights persisted; no `/ml/predict`, no scheduler, no F5 adapter reuse.

## Architecture Decisions

| ID | Choice | Rejected | Rationale |
|---|---|---|---|
| M-A1 | `ml/` package + `services/ml_service.py` + `api/v1/ml.py`, parallel to F5 | reusing `probability/` internals | engine isolation contract; F5 `_StatsReaderAdapter` imports nonexistent `models.stat_value` (verified `prob_service.py:110-111`) — never import it (MLE-06) |
| M-A2 | dict-dispatch `registry.py`; `model_set` gate (`core-5` executes, `future-ml` declared) | Kahn DAG (F4-style) | models are independent (F5 D-A2 precedent); scope gate is the isolation boundary (MLE-07) |
| M-A3 | `snapshot_store.py` consolidates header+payload I/O (F5 `SnapshotStore` clone) | two repos | single `ml_*` I/O owner; lifecycle enforced here (MLE-08) |
| M-A4 | metrics as `ml_metrics` rows `(model_id, model_version, number, metric_name, value, params_json)` | per-model tables | normalized, checksum-friendly; `value Numeric(20,8)` |
| M-A5 | `ML_FEATURE_ORDER = ("consecutive_count", "current_frequency", "decade_distribution", "draw_mean", "draw_range", "draw_sum", "low_high_ratio", "max_current_gap", "odd_even_ratio", "repeated_from_previous")` — the 10 F4 core ids in canonical sorted order (F4 `_build_rows` persists `sorted(execution.values)`, verified) | implicit registry iteration | fixed column order is part of the fingerprint contract (MLE-03/05); test asserts tuple equality |
| M-A6 | `ML_GENERATOR_VERSION = "1.0.0"` in `ml/__init__.py` | reusing FEATURE version | per-engine identity, bumped only when output changes (F4/F5 parity) |
| M-A7 | metrics from `sklearn.metrics` (accuracy/precision/recall/f1/roc_auc) quantized `Decimal(str(x)).quantize(Decimal("0.00000001"))` before checksum/persist (D4) | raw float columns | float never enters fingerprint/checksum/storage (MLE-05) |
| M-A8 | `cut` passed per run (default `len(draws) * 4 // 5`); validator rejects eval rows ≤ cut | fixed 80% constant | explicit cut participates in fingerprint (MLE-03/EC-02) |
| M-A9 | sklearn exact-pinned in `pyproject.toml` deps; `xgboost/lightgbm/catboost/networkx` absent; CI banned-import test | full stack | D1; F6 ban-gate precedent `graph/__init__.py` |

Rejected with `probability/` also: predicting via F4 `StatisticsProvider` (F5 option), persisting weights/joblib blobs (MLE-01), auto-retire/scheduler (MLE-09).

## Module Map (`backend/src/backend/app/ml/`)

| File | Responsibility | Traces |
|---|---|---|
| `__init__.py` | `ML_GENERATOR_VERSION="1.0.0"` (the only seam kept) | MLE-05 |
| `features.py` | `ML_FEATURE_ORDER` tuple + ids (the explicit F4 contract) | MLE-03/05 |
| `providers.py` | `DrawReader`, `FeatureSnapshotReader`, `StatSnapshotReader` Protocols + carries (`DrawRow`, `LotteryRules`, `FeatureVector`) | MLE-06 |
| `registry.py` | `FamilyDefinition` (id/version/params/builder) + dict dispatch; `build_ml_registry()` registers 5 `core-5`; declares 3 `future-ml` (`xgboost`,`lightgbm`,`catboost`) versioned, never executing | MLE-07 |
| `fingerprint.py` | canonical SHA-256 (mirror `feature_engineering/fingerprint.py` `_jsonable`) over {draws checksum, feature order, params, cut, `ML_GENERATOR_VERSION`} | MLE-05 |
| `determinism.py` | `quantize_metric(x) -> Decimal("…")`; `metric_checksum(rows)` over quantized content | MLE-05, D2 |
| `walk_forward.py` | `split(draw_numbers, cut)` → (train ≤ cut, eval > cut); `validate_split(strict)` rejects any eval row ≤ cut (leakage) | MLE-03 |
| `engine.py` | pure train: builds frame (X per n from F4 rows, y per number k in draw n+1), fits each family `random_state=0`, predicts, computes quantized metrics | ME-01..05 |
| `snapshot_store.py` | `MlSnapshotStore` — clone of F5 `SnapshotStore` for `ml_*`: active, find-by-fingerprint, next-version, ordered bulk insert, retire-old-active, failed | MLE-08 |
| `schemas.py` | `TrainRequest`, `MlModelsList`, `MetricsRead` (mirror `schemas/probability.py`) | MLE-09 |

Service: `services/ml_service.py` — `generate(lottery_code/id, model_set, cut, scope)` and reads; API `api/v1/ml.py`; plus `cli.py` subcommands `lip ml train|models|metrics`.

## Data Model & Migration 0009_ml_tables

`models/ml_snapshot.py` + `models/ml_value.py` (`ml_metrics` table) — registered in `models/__init__.py` for `Base.metadata`.

`ml_snapshots`: `id PK · lottery_id FK RESTRICT · model_set String(32) (== "core-5") · version String(32) · ml_generator_version String(32) · checksum String(64) · input_fingerprint String(64) · cut int NOT NULL · status String(16) CHECK IN (active,retired,failed) · is_locked · draw_count · draws_from · draws_to · created_at · updated_at · Unique(lottery_id, model_set, version) · Check(draws_from <= draws_to)`.

`ml_metrics`: `id PK · snapshot_id FK RESTRICT · model_id String(64) · model_version String(32) · number Integer (target) · metric_name String(32) (accuracy|precision|recall|f1|roc_auc) · value Numeric(20,8) · params_json Text (frozen hyperparams only) · Unique(snapshot_id, model_id, number, metric_name)`.

`alembic/versions/0009_ml_tables.py` (down_rev `0008_graph_tables`): `upgrade` creates `ml_snapshots`, `ml_metrics`, indexes `ml_snapshots (lottery_id, model_set, status)`, `ml_metrics (snapshot_id, model_id)`; `downgrade` drops ONLY `ml_*` (MLE-10). Additive — copies `0008` cosmetic.

## Provider Seams (`providers.py` — Protocols only, F5 bug OUT)

```python
class DrawReader(Protocol):
    def iter_draws(self, lottery_id, *, after_draw_number=None) -> Iterator[DrawRow]: ...   # ORDER BY draw_number, id
    def lottery_rules(self, lottery_id) -> LotteryRules: ...
class FeatureSnapshotReader(Protocol):
    def active(self, lottery_id, feature_set="core") -> FeatureRef | None: ...   # active feature snapshot id
    def rows(self, snapshot_id) -> Iterable[FeatureValueRow]: ...                # (feature_id, draw_number, value) Decimal
class StatSnapshotReader(Protocol):
    def active(self, lottery_id, metric_set="core") -> StatsRef | None: ...      # optional; None → skipped, never guessed
```
Service adapters wrap `DrawRepository`, `FeatureEngineService.read_features` / `FeatureValueRepository`, `StatisticsService.get_active` — never `probability_service`. Missing feature snapshot → raise `SnapshotNotFoundError` (`SNAPSHOT_NOT_FOUND` 404) BEFORE training (MLE-06). Zero draws → `ValidationError` clean message (MLE-12), no snapshot written.

## Determinism & Persistence Contract (implementable steps)

1. Resolve lottery; read draws (ordered); read active F4 snapshot rows for the 10 ids; build per-draw `X` in `ML_FEATURE_ORDER` columns; `y_k` per number `k` ∈ [min,max] from draw n+1.
2. Compute `input_fingerprint` (fingerprint.py) over {draws checksum, lottery_id, feature ids+versions, params, cut, ML_GENERATOR_VERSION}.
3. Walk-forward split via `walk_forward.split` (train ≤ cut, eval > cut); if any eval row ≤ cut → raise `LeakageError`; no writes. (anti-shuffle)
4. Train: for each family in core-5 → fit per number (RF/ET/GB/SVM `random_state=0`; KNN deterministic), predict eval, metrics `accuracy,precision,recall,f1,roc_auc` — quantized Decimal(20,8) → Decimal/str.
5. `checksum` = SHA-256 over the canonical JSON of the QUANTIZED metric rows (`Model_id|model_version|number|metric_name|value`). Float never persists.
6. Persist atomic (MLE-08): `create_snapshot(active, locked)` → `bulk_insert_values` → `retire_old_active` → commit; on exception rollback + terminal `failed` header.
7. Idempotent: `scope="incremental"` returns existing active when `input_fingerprint` matches (no duplicate version); reads serve stored rows only, 404 when absent (MLE-09).

`cut` participates in fingerprint so a different cut always yields a new version.

## Anti-Leakage Design (walk-forward, cut semantics)

```
draws ordered:      1 ... cut ... N-1   (targets = draw n+1 for row n)
train rows:  n in [1, cut];                        eval rows: n in (cut, N-1]
X = features at draw n (from F4 snapshot)          y_k(n) = 1 iff k in draw n+1
```

`validate_split(existing_split, cut)` re-validates; a shuffled/eval-before-cut candidate MUST raise pure `LeakageError` (unit + RED test). RED test also asserts the walk-forward train/eval index sets are proper subsets (no intersection of draw_numbers). Cut stored in snapshot header; a differing cut is a new fingerprint.

## F4 Backend-Delta Preservation (approx. checkpoint)

F3 `backend` spec REQ-10/11/12 currently define the statistics surface; the delta `specs/backend/spec.md` **MODIFIED** each requirement, appending the ML endpoints WITHOUT deleting any existing scenario the delta includes the previous scenarios verbatim (generation is manual only; unknown lottery → 404; read never precompute; missing snapshot signals; CLI generates + CLI trains). The existing `openspec/specs/backend/spec.md` we read confirms REQ-10/11/12 scenarios stay; new ML scenarios are strapped to. Parity: existing `tests/statistics/test_statistics_api.py`, `tests/api/test_statistics_api.py`, `statistics.py` router/CLI NOT touched; `tests/ml/test_ml_backend_parity.py` runs both the untouched `POST /statistics/generate` and new `POST /ml/train`, reads prove stats surface still 200 + ML additive-only (verified by `git diff` scope). No test reuse a dataset fixture.

## Future-ML Isolation (`model_set="core-5"` only)

- `registry.py` `register("xgboost")/register("lightgbm")/register("catboost")` with `status="declared"`, `category="future-ml"`, `version="1.0.0"`, NO builder/fit.
- No `import xgboost|lightgbm|catboost|networkx` anywhere (`ml/` AND service — the isolated package test scans `vars(module)` names, mirrors `tests/probability/test_providers.py` `_FORBIDDEN_SUBSTRINGS`).
- Not in `pyproject.toml` deps (allowlist denial test greps pyproject for the 4 names).
- `test_registry_scope_hoods.py`: `core-5` registry builds exactly 5 executed ids; `future-ml` builds 3 declared ids with zero persisted rows after a run (GF2(b) parity); unknown family → `ValidationError` listing known ids.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit | eng frame/split/metrics/quantization | fixtures; assert Decimal type in every metric row; identical quantized metrics on rerun |
| Unit determinism | fingerprint+checksum byte-identical twice (GF1) | two independent tmp migrated DBs; assert header checksum/fingerprint/rows identical (precedent `tests/test_determinism.py`) |
| Anti-shuffle RED | `test_walk_forward_leakage_rejected.py` | shuffled candidate raises `LeakageError`, 0 rows written; walk-forward passes |
| Migration | 0009 upgrade/downgrade | `tests/test_migrations.py`: upgrade head adds `ml_*`; downgrade removes ONLY `ml_*` (Core/stat/feature/prob/graph intact) |
| Lifecycle | active→retired in same tx; fail→`failed` header only | `test_snapshot_store.py` parity |
| API/CLI parity | POST /ml/train + GETs; `lip ml …` | TestClient + subprocess CLI, snapshot-read-only reasoning 404; stats surface untouched baseline |
| Isolation | registry `core-5` vs `future-ml`; deps | `test_registry_scope_isolates.py` + pyproject grep |

Threat Matrix: N/A — no routing/shell/subprocess/PR automation; all additions are existing argparse/FastAPI smoke surface (parity with F5 archive D2).

## File Changes / PR Breakdown

PR 1 — deps+models (≈230): `pyproject.toml` (pin `scikit-learn>=1.4,<2`; numpy), `models/ml_snapshot.py`, `models/ml_metric.py`, `models/__init__.py` (register 2), `alembic/versions/0009_ml_tables.py`, `tests/test_migrations.py` (0009 rows).

PR 2 — config+registry+gates (≈380): implement `ml/{__init__,features,providers,registry,fingerprint,determinism}.py`; `tests/ml/test_registry_isolation.py` (core-5 executes, future declared), `tests/ml/test_fingerprint.py`, `tests/test_providers.py` style no-concrete-seam + banned-import tests.

PR 3 — engine+split+leakage (≈400): `ml/engine.py`, `ml/wf.py` (walk-forward + validate), `tests/ml/test_engine.py`, `tests/ml/test_walk_forward.py`.

PR 4 — persistence+service (≈400): `ml/snapshot_store.py`, `services/ml_service.py` (+ errors reuses `GenerationError`, `SnapshotNotFoundError`), `tests/ml/test_snapshot_store.py`, `tests/ml/test_ml_service.py`.

PR 5 — API + CLI (≈400): `api/v1/ml.py`, `schemas/ml.py`, mount `router.py`; `cli.py` `ml` subcommands; `tests/api/test_ml_api.py`, `tests/api/test_ml_cli.py`. Stats routes untouched.

PR 6 — e2e+docs (≈300): `tests/ml/test_ml_determinism_e2e.py` (two seeded DBs via CLI+API), `tests/ml/test_ml_parity_stats.py`, README/PROJECT_STATUS/IMPLEMENTATION_ROADMAP updates.

## Traceability

MLE-01→models+0009+store · MLE-02→store writes only `ml_*` + read-only test · MLE-03→walk_forward · MLE-04→registry core-5 · MLE-05→fingerprint+determinism · MLE-06→providers · MLE-07→registry scope · MLE-08→snapshot_store lifecycle · MLE-09→API/CLI reads only · MLE-10→0009 downgrade · MLE-11→lottery_id FK everywhere · MLE-12→empty-DB ValidationError fixtures · ME-01..05→engine per family.

## Migration / Rollout

0009 downgrade drops only `ml_*`; pin rollback via `pyproject` revert. No scheduler/flags. Manual CLI/API only.

## Risks

| Risk | L | Mitigation |
|---|---|---|
| Runtime ban-gate drift | H | no imports + deps allowlist; CI assert |
| sklearn cross-env byte drift | M | same-env guarantee only; quantized checksums |
| Data leakage | H | `validate_split` + anti-shuffle RED test |
| Cut/frame mismatch skew | M | fingerprint includes cut; stored cutoff column |
| F5 adapter re-temptation | M | own provider Protocols; no `probability_service` import (test-forbidden) |

## Open Questions

None blocking — every element traces to MLE-01..12 / ME-01..05 or D1..D6.