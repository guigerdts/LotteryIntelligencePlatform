# Fase 16 — Performance: Exploration

- Status: **complete**
- Store: **openspec**
- Change: `fase-16-performance`
- Scope: exploration ONLY — no implementation, no code modification, no commits/PRs
- Method: read-only inspection + real measurements (pytest durations per-directory, cProfile on representative paths, SQLite index/schema inspection, EXPLAIN-equivalent analysis)

---

## 1. Executive summary

The platform's **database layer is already well-indexed** by migrations 0002/0004 and the per-engine snapshot migrations (0015). The production `backend/lottery.db` is an empty, un-migrated dev file (0 draws, no perf indexes applied) — **not** representative. The REAL hot paths are **CPU-bound engine computation**, not SQL: ML training (≈245 sequential sklearn fits per full train), backtest window evaluation, and torch DL determinism. Two concrete SQL problems exist: an **N+1 in `bt_service._fetch_draws`** (1 query per draw) and the **experiment comparison cache scan** (`exp_service._find_cached_comparison` parses every comparison JSON blob). The dominant test-suite cost is **fixture setup ≈3s/test** plus **torch import ≈25-31s per process** — a TEST-ENV concern, not a production hot path. Two environment defects block real functionality: **`deap`/`optuna` are declared but NOT installed** (opt GA/bayesian unusable → 5 test failures), and a **latent `StatValue` import bug** in `probability_service._StatsReaderAdapter.frequencies` crashes probability generation whenever an active statistics snapshot exists.

Environment: 7.4 GB RAM (≈2.4 GB available), 8 GB swap (3.5 GB used), 3 cores, Python 3.13.7, torch 2.13.0+cpu, scikit-learn 1.6.1.

---

## 2. Baseline medible

| Component | Metric | Value | How measured | Env tag |
|---|---|---|---|---|
| Statistics `generate` (2000 draws) | total time | **0.90 s** | cProfile, tmp migrated SQLite | REAL |
| — compute payload | cumtime | 0.55 s (iter_draws 0.43 s) | cProfile | REAL |
| — persist (bulk insert) | cumtime | 0.34 s | cProfile | REAL |
| Statistics reads (freq + gaps) | total time | **0.06 s** | cProfile | REAL |
| ML train (1 family, `test_train_basic`) | call | **8.18 s** | pytest `--durations` | REAL |
| ML engine train basic | call | 5.37 s | pytest | REAL |
| ML determinism e2e (2 runs) | call | 1.99 s | pytest | REAL |
| BT API run 200 | call | 6.35 s | pytest | REAL |
| BT e2e CLI full cycle | call | 5.79 s | pytest | REAL |
| DL determinism LSTM 2 runs | call | 5.20 s | pytest | REAL |
| DL `test_configure_deterministic_torch_sets_seed` | call | **22.69 s** | pytest | REAL (torch CPU) |
| Statistics g9 determinism test | call | 7.43 s | pytest | BOTH |
| Exp API setup (seeds engine runs) | setup | 4–14 s/test | pytest | BOTH |
| Fixture setup (per-test DB + app) | setup | ~3 s/test (stats/api/gen/fe) | pytest | TEST-ENV |
| Cold start `import backend.app.main` | wall | **25.3 s** | `time python -c import` | BOTH |
| `import torch` | wall | **31.4 s** | `time` | BOTH |
| `import sklearn` | wall | 12.8 s | `time` | BOTH |
| Dev DB `lottery.db` | rows | 0 draws; no perf indexes | sqlite3 | TEST-ENV |
| Migrated DB (head=0015) | indexes | 41 non-auto indexes incl. all snapshot `_status` + payload `_snapshot_id` | alembic upgrade + sqlite3 | REAL |

Suite times (per-directory, `-q --durations=20 -p no:warnings`, generous timeouts; full suite intentionally NOT run — known hang on memory-limited box):

| Directory | Result | Time |
|---|---|---|
| tests/statistics | 20 passed | 32.9 s |
| tests/probability | 80 passed | 11.3 s |
| tests/api | 23 passed | 78.4 s |
| tests/ai | 29 passed | 1.3 s |
| tests/ml | 3 passed | 13.3 s |
| tests/bt | 170 passed, **2 failed** (migration) | 239.2 s |
| tests/gen | 145 passed | 149.6 s |
| tests/meta | 138 passed | 9.0 s |
| tests/graph | 116 passed | 8.6 s |
| tests/dl | 127 passed | 84.1 s |
| tests/feature_engineering | 48 passed | 42.4 s |
| tests/opt | 124 passed, **5 failed** (missing deps) | 26.3 s |
| root crud/import/services | 113 passed | 259.6 s |
| root exp | 83 passed | 242.2 s |
| root misc (smoke, ml_pr*, migrations, integrity…) | 138 passed, **6 failed**, 1 skipped | 342.2 s |

Σ ≈ **1 540 s ≈ 26 min** for the per-directory sweep (excluding re-runs). Worst offenders by time: root misc (5.7 min), root crud (4.3 min), root exp (4.0 min), bt (4.0 min).

---

## 3. Inventario de hotspots (ranked)

| # | Hotspot | Location | Severity | Env tag |
|---|---|---|---|---|
| 1 | ML training: 5 families × 49 numbers sequential sklearn fits | `ml/engine.py:124-135`, `services/ml_service.py:74-81` | High | REAL |
| 2 | BT window evaluation: sequential windows × 3 predict passes | `backtesting/engine.py:94-130` | High | REAL |
| 3 | BT draw-history load N+1 (1 query per draw) | `services/bt_service.py:205-213` (`_fetch_draws`) | Medium | REAL |
| 4 | Exp compare cache: full scan + `json.loads` of every comparison blob | `services/exp_service.py:410-424` | Medium | REAL |
| 5 | Cold start: `import backend.app.main` 25 s (torch transitive) | `main.py` import graph | Medium | BOTH |
| 6 | Test fixture setup ~3 s/test (per-test migrated DB + app boot) | `tests/conftest.py:38-88` | High (test only) | TEST-ENV |
| 7 | Torch determinism setup 22.7 s | `dl/determinism.py` (seed config) | Low | REAL |
| 8 | Graph `compute` N+1 (per-draw `read_draw_numbers`) | `services/graph_service.py:141` | Low (batch) | REAL |
| 9 | Missing runtime deps `deap`/`optuna` | `pyproject.toml:45,52` vs `.venv` | High (blocks opt) | TEST-ENV |
| 10 | Latent `StatValue` import bug in probability stats reader | `services/probability_service.py:110` | High (crash) | REAL |
| 11 | AI service loads all prob values per call | `services/ai_service.py:115-120` | Low | REAL |
| 12 | `read_frequencies` fetch-all-then-slice (`last`) | `services/statistics_service.py:135-144` | Low | REAL |
| 13 | Probability MC computed twice per generate | `services/probability_service.py:323-330, 366-375` | Low | REAL |
| 14 | Migration-test expectation drift (6 failures) | `tests/test_migrations.py` | Low (suite health) | BOTH |

---

## 4. Evidencia/mediciones por hotspot

### H1 — ML training (REAL, CPU-bound)
- **Evidence**: `tests/ml` durations — `test_train_basic` 8.18 s, `test_engine_train_basic` 5.37 s, `test_anti_shuffle_rejected` 4.68 s, `test_engine_walk_forward_respects_cut` 4.02 s.
- **Reproduction**: `ml/engine.py:124-135` — `for number in all_numbers: model.fit(X_train, y[number][train_idx])` is strictly sequential; `MlService.train` (ml_service.py:74-81) loops 5 families sequentially. Each fit is independent → 245 independent fits for a full train (49 numbers × 5 families).
- **Measurement**: calls above; core count 3.
- **Assessment**: CPU-bound, embarrassingly parallel (per-number, per-family). Determinism preserved if RNG/order fixed (engine already never shuffles, D2).

### H2 — BT window evaluation (REAL, CPU-bound)
- **Evidence**: `tests/bt` durations — `test_run_returns_200` 6.35 s, `test_cli_full_cycle` 5.79 s, `test_results_by_snapshot_id` 5.56 s, per-snapshot tests 5.3-5.4 s.
- **Reproduction**: `backtesting/engine.py:94-130` — for each window, 3 predict passes (`strategy` + `uniform` + `hyper`) over eval draws, sequential. Windows are independent (expanding-window contexts) — parallelizable.
- **Measurement**: 5-6 s per full run on ~thousands of draws.
- **Assessment**: CPU-bound; window independence makes `ProcessPoolExecutor` viable; must preserve deterministic result order.

### H3 — BT `_fetch_draws` N+1 (REAL, SQL)
- **Evidence**: `bt_service.py:205-213` — inside `for d in execute(select(DrawModel)...).scalars().all():` there is a nested `execute(select(DrawNumber).where(DrawNumber.draw_id == d.id))`. 1 query per draw.
- **Reproduction**: any `BtService.run()`; for 2 000 draws ≈ 2 001 SELECTs.
- **Measurement**: `ix_draw_numbers_draw_id` exists (fast per query) but the round-trip count dominates; `DrawRepository.list_draws` (draw_repository.py:67-87) already shows the correct pattern (`selectinload`).
- **Assessment**: clear N+1; fix = `selectinload(Draw.numbers)` on the draw query. Low risk.

### H4 — Exp compare cache scan (REAL, SQL + JSON)
- **Evidence**: `exp_service.py:410-424` — `select(ExpComparison).where(experiment_id == ...)` loads ALL comparisons, then `for comp ... json.loads(comp.comparison_json)` parses every blob to compare run ids.
- **Reproduction**: `ExpService.compare()` with cached comparisons present; O(N_comparisons × blob_size) JSON parsing per call.
- **Measurement**: `ix_exp_comparisons_experiment` exists; the cost is Python-side whole-blob JSON parse per row, not SQL.
- **Assessment**: blobs are immutable; a denormalized `run_ids`/fingerprint column (indexed) removes parsing entirely.

### H5 — Cold start 25 s (BOTH)
- **Evidence**: `time python -c "import backend.app.main"` = 25.3 s; `import torch` alone 31.4 s; `import sklearn` 12.8 s.
- **Measurement**: as above.
- **Assessment**: One-time per process → TEST-ENV dominates (every pytest process pays it once; per-test `client` fixture re-creates the app but module imports are cached). For a long-lived uvicorn server it is a single boot cost → REAL but low impact; worth deferred/lazy torch import.

### H6 — Fixture setup ~3 s/test (TEST-ENV)
- **Evidence**: `tests/statistics`, `tests/api`, `tests/gen`, `tests/feature_engineering`, root tests all show **setup ≈ 2.5-3.9 s/test**; `tests/probability` and `tests/meta`/`tests/graph` (smaller fixtures) show setup 0.1-0.6 s.
- **Reproduction**: `conftest.py:38-88` — `migrated_db` runs `alembic upgrade` to head on a fresh tmp file per test; `client` bootstraps a fresh app per test.
- **Measurement**: 23 API tests in 78.4 s ≈ 3.1 s/test setup.
- **Assessment**: pure test-env cost; session-scoped DB + shared migrated file + single app import would cut most of it. NOT a production issue.

### H7 — Torch determinism 22.7 s (REAL)
- **Evidence**: `test_configure_deterministic_torch_sets_seed` call 22.69 s.
- **Reproduction**: torch CPU seed/thread configuration cost.
- **Assessment**: REAL but one-shot per process; low priority.

### H8 — Graph compute N+1 (REAL, batch)
- **Evidence**: `graph_service.py:141` — `draw_numbers = [self._reader.read_draw_numbers(did) for did in draw_ids]`; `_DrawReaderAdapter.read_draw_numbers` runs a query per draw.
- **Measurement**: per-draw query is index-backed; cost grows linearly with draw count. Batch/admin path only.
- **Assessment**: fix via a single batched join; low priority.

### H9 — Missing deps `deap`/`optuna` (TEST-ENV → blocks REAL)
- **Evidence**: `.venv/bin/pip list` shows neither; `tests/opt` → 5 failures (`test_bayesian_*` ModuleNotFoundError; `test_all_implement_protocol`).
- **Reproduction**: `python -c "import deap"` → ModuleNotFoundError.
- **Assessment**: venv is stale vs `pyproject.toml` (not a perf bug, but the opt engine's GA/bayesian paths are un-executable → cannot be measured).

### H10 — Latent `StatValue` bug (REAL correctness)
- **Evidence**: `probability_service.py:110` imports `backend.app.models.stat_value` which does not exist (models/ has `stat_average`, `stat_frequency`, `stat_gap`, `stat_scalar`, `stat_snapshot` — no `stat_value`). Verified `ModuleNotFoundError`.
- **Reproduction**: `probability generate` with an active statistics snapshot → `_compute_execution` reaches `self._stats_reader.frequencies(stats_ref.id)` → crash. Probability tests pass only because no stats snapshot is seeded.
- **Assessment**: correctness bug in a hot orchestration path; must be fixed (align with `stat_frequency` or similar) before any perf work on probability.

### H11 — AI service loads all prob values (REAL, low)
- `ai_service.py:115-120` reads every `prob_value` row per interpret/report/assist call. Snapshot sizes are bounded (~200-300 rows); low impact.

### H12 — `read_frequencies` fetch-all-then-slice (REAL, low)
- `statistics_service.py:135-144` loads all `stat_frequency` rows then slices `[:last]` in Python; `last` is not pushed to SQL (unlike `SnapshotStore.values_for_snapshot` which does `limit`). Low impact.

### H13 — Probability MC double compute (REAL, low)
- `probability_service.py:323-330` runs `monte_carlo` with a placeholder seed, then 366-375 re-runs it with the real fingerprint seed. 2× MC cost (≤10 000 sims each). Determinism requires the second run; the first could be skipped.

---

## 5. Problemas SQL concretos

| # | Query / model / repo | Issue | Evidence |
|---|---|---|---|
| 1 | `bt_service._fetch_draws` (bt_service.py:205-213) | **N+1**: 1 SELECT per draw for `DrawNumber` | nested `execute` inside draw loop |
| 2 | `graph_service.compute` → `_DrawReaderAdapter.read_draw_numbers` (graph_service.py:141, 69-79) | **N+1**: 1 SELECT per draw during graph build | list-comprehension over draw ids |
| 3 | `exp_service._find_cached_comparison` (exp_service.py:410-424) | **Full-table scan + whole-blob `json.loads` per row**; no run_ids column/index | loop parses `comparison_json` for every row of the experiment |
| 4 | `statistics_service.read_frequencies/read_gaps` (statistics_service.py:135-158) | **Fetch-all-then-slice**: `last` bound applied in Python, not SQL | `list(rows)[:last]` after `.all()` |
| 5 | Dev DB `lottery.db` | No perf indexes, 0 rows — **not** representative of production schema | sqlite_master shows only auto indexes; alembic chain 0002/0004 defines them |
| 6 | Payload reads (`prob_values`, `stat_frequency`, `graph_values`, `ml_metrics`, `feature_values`) | **No issue**: `snapshot_id` is leading column of UNIQUE constraints AND has explicit `ix_*_snapshot_id` | migrated schema inspection |
| 7 | Snapshot-header reads by `(lottery_id, *, status='active')` | **No issue**: explicit `ix_*_lottery_*_status` indexes exist in migrations | migrated schema inspection |
| 8 | `exp_comparisons.comparison_json`, `bt_results.*_json` | **Large JSON Text blobs** read via `json.loads` in read paths (exp compare scan, bt results read) | exp_service.py:420, bt_service.py:188-189 |

**Index inventory (migrated DB, head=0015)**: 41 explicit indexes cover the snapshot headers (`ix_snap_lottery_metric_status`, `ix_psnap_lottery_model_status`, `ix_fsnap_lottery_set_status`, `ix_gsnap_lottery_type_status`, `ix_msnap_lottery_model_status`, `ix_dsnap_lottery_model_status`, `ix_osnap_lottery_optimizer_status`, `ix_bt_snapshots_lottery_strategy`, `ix_gen_snapshots_lottery_selection`, `ix_meta_selections_lottery_context`, `ix_exp_experiments_lottery_status`) and payloads (`ix_stat_frequency_snapshot_id`, `ix_pval_snapshot_id`, `ix_fval_snapshot_id`, `ix_gval_snapshot_id`, `ix_mval_snapshot_id`, `ix_dval_snapshot_id`, `ix_dweight_snapshot_id`, `ix_bt_results_snapshot_id`, `ix_oresult_snapshot_id`, `ix_gen_combinations_snapshot`) plus core draw/import indexes. The SQL layer is largely sound.

---

## 6. Oportunidades de caché

| What is recomputed | Where | Impact |
|---|---|---|
| Experiment comparison is cached as JSON already, but cache lookup re-parses every blob | `exp_service.py:410-424` | Med — fix the lookup (dedup key column), the cache itself is fine |
| Snapshot reads are immutable but re-queried on every request (stats/prob/graph/ml reads hit DB each time) | `statistics_service.read_*`, `probability_service.read_values`, `graph_service.read`, `ml_service.get_metrics`, `bt_service` results | Med — snapshots are immutable + versioned: an in-process/HTTP cache keyed on `(snapshot_id, endpoint)` or ETag would serve repeated reads from memory |
| AI assistant re-reads freq/gaps/averages + all prob values per call | `ai_service.py:94-120` | Low-Med — could read once per snapshot version |
| `read_frequencies` re-fetches all rows even for `last=N` | `statistics_service.py:135-144` | Low — push `last` to SQL |
| Probability MC double compute | `probability_service.py:323-330, 366-375` | Low — skip the placeholder run |
| Generated snapshots returned idempotently only during generation; reads never consult fingerprints | all services | Low — already mostly correct (STE-10/PES-08 never precompute) |

Cache-compatible property: all snapshot payloads are immutable and versioned, so caching on the snapshot version is sound and requires no invalidation beyond "new snapshot version".

---

## 7. Oportunidades de paralelización

| Independent work | Where | Impact | Notes |
|---|---|---|---|
| 5 ML families (and 49 per-number fits within each) are independent | `ml_service.py:74-81`, `ml/engine.py:124-135` | High — ≈245 sequential fits; 3 cores available | Determinism: engine never shuffles; must freeze result ordering + RNG per worker |
| Backtest windows (strategy/benchmark predict passes) are independent | `backtesting/engine.py:94-130` | Med-High — 5-6 s/run | Deterministic split; order results by window_index |
| DL LSTM/MLP training per family | `dl/engine.py`, `dl_service` | Med — torch already parallelizes internally on CPU threads; extra process-level parallelism has diminishing returns on 3 cores |
| Probability method registry (each method is independent; MC is the heavy one) | `probability_service.py:296-352` | Low-Med — methods are cheap; MC ≤10k sims |
| Multi-lottery generation loops (if any batch CLI) | `cli.py` batch paths | Low — no batch multi-lottery loop found; single-lottery per call |

GIL note (code-optimization skill): these are **CPU-bound** → must use `ProcessPoolExecutor`/`multiprocessing`, never threads. Given only 3 cores and the memory-limited box, parallelism must be bounded (e.g. max_workers ≤ 2-3) and careful about pickling large numpy/DB objects.

---

## 8. Memoria y tiempos

- **Box**: 7 435 MB total, ≈2 401 MB available, 8 GB swap (3 526 MB used), 3 cores. The known full-suite hang under ~1 GB available memory is consistent with this box's headroom: heavy dirs (bt, dl, root exp) run OK per-directory (measured) but the full suite in one process risks OOM. **TEST-ENV-only**, not a production issue.
- **Import cost**: `backend.app.main` 25.3 s; `torch` 31.4 s; `sklearn` 12.8 s. Paid once per process. **BOTH** (server boot REAL, per-test TEST-ENV).
- **Fixture cost**: ~3 s/test setup for app-backed dirs (alembic upgrade + app boot); probability/meta/graph dirs with lighter fixtures run 0.1-0.6 s setup. **TEST-ENV-only**.
- **Engine memory**: statistics generate is O(BATCH_SIZE) via keyset pagination (documented STE-08) — measured 0.90 s/2 000 draws; payload builds full in-memory dicts (~1-2 MB for 2 000 draws) — acceptable. ML keeps 49 fitted models in memory per family (TrainResult.models) — grows with number pool; bounded by lottery rules. **REAL, low**.
- **Cold-start memory spike**: torch import reserves CPU threads/workspace on import; on a 2.4 GB-available box this is a real contributor to the full-suite OOM. **TEST-ENV**.

---

## 9. Riesgos y tradeoffs (por fix propuesto)

| Fix | Benefit | Effort | Risk |
|---|---|---|---|
| `bt_service._fetch_draws` selectinload | Removes N+1; modest speedup | Low | Low — same rows, one round-trip |
| `exp_service` compare: add indexed `run_ids` column | Eliminates blob-scan; near-constant compare lookup | Low-Med | Migration + backfill of existing rows; keep legacy path during transition |
| ML per-number/per-family parallelism (ProcessPool) | 2-3× train speedup on this box | Med-High | **Determinism**: must preserve fit ordering and RNG isolation; sklearn `n_jobs` interplay; pickle overhead for 49 models; memory ×workers |
| BT window parallelism | 2-3× on window count | Med | Ordering determinism; process overhead on small windows |
| Snapshot read cache / ETag | Cuts repeated immutable reads | Med | Invalidation must key on snapshot version only; no write-through needed (immutable) |
| Deferred/lazy torch import | Cold start 25 s → ~seconds | Low-Med | Import-time side effects (e.g. thread config) must move to first use |
| Session-scoped test DB fixture | 3 s/test → ~0.1 s/test setup | Low | Test isolation regression risk; must guarantee per-test data reset |
| Fix `StatValue` bug | Unblocks probability generate with stats present | Low | None (bug fix) |
| Install `deap`/`optuna` | Unblocks opt GA/bayesian | Low | Environment only; outside Fase-16 scope unless opt is in scope |
| Migration-test expectation refresh | Restores 6 failing tests | Low | None — aligns test to 0015 chain |

Cross-cutting risk: **all parallelism and caching must preserve the determinism contract** (GF-1 byte-identical generations). Every engine has fingerprint/checksum gates; any parallel path must freeze iteration order and RNG seeds, and be verified by the existing determinism tests.

---

## 10. Propuesta de alcance para Fase 16

Priority ordering (impact ÷ effort ÷ risk):

1. **P0 — Correctness first**: fix latent `StatValue` bug (probability generate) + restore/refresh migration tests (suite health). Tiny effort, unblocks probability and 6 failing tests.
2. **P1 — SQL read-path fixes** (low risk, real win): `_fetch_draws` selectinload; `read_frequencies`/`read_gaps` LIMIT pushdown; exp compare `run_ids` indexed column. Expected: BT run −20-30%, compare near-constant.
3. **P2 — Engine parallelization** (highest ceiling): ML per-number/per-family `ProcessPoolExecutor` and BT window parallelism. Expected 2-3× on the two heaviest real endpoints. Highest risk → needs determinism verification slice.
4. **P3 — Snapshot read cache / ETag**: immutable-snapshot cache on reads (stats/prob/graph/ml/bt). Expected: repeated dashboard reads near-0 DB cost.
5. **P4 — Cold start**: lazy torch import + deferred heavy deps. Expected: import 25 s → seconds.
6. **P5 — Test infra** (explicitly separate from production): session-scoped migrated DB fixture to cut the ~3 s/test setup; documents the 1 GB-memory full-suite limitation.

Out of scope for Fase 16: frontend (measured clean — memoized, no polling), SQL index additions (already covered by migrations), deap/optuna install (environment).

---

## 11. Posibles slices de implementación (PROPOSAL ONLY — no implementation)

Each slice ≤ 400 authored lines, reviewable, dependency-ordered:

1. **S1 — Correctness unblock** (`fix`): replace `stat_value` import/query in `probability_service._StatsReaderAdapter` with the real `stat_frequency` payload; add a regression test for probability generate with an active stats snapshot. Depends on: none.
2. **S2 — Read-path SQL** (`perf`): `bt_service._fetch_draws` → `selectinload(Draw.numbers)`; push `last` LIMIT into `statistics_service.read_frequencies/read_gaps`; add `run_ids` indexed column to `exp_comparisons` + migration + backfill + update `_find_cached_comparison` to a single indexed lookup (keep legacy path while migrating). Depends on: S1 (same files touched).
3. **S3 — BT parallelization** (`perf`): evaluate windows via bounded `ProcessPoolExecutor`, deterministic ordering by `window_index`, determinism tests unchanged. Depends on: S2 (touches bt_service).
4. **S4 — ML parallelization** (`perf`): parallelize per-number fits (and optionally per-family) with bounded process pool, frozen RNG/order, determinism gate via existing `test_ml_*`/`test_determinism` tests. Depends on: none (independent of S2/S3).
5. **S5 — Snapshot read cache / ETag** (`perf`): keyed cache on `(snapshot_id, endpoint)` for immutable snapshot reads + `ETag`/`304` on read endpoints; no write-through (immutability). Depends on: S1 (probability read path correctness first).
6. **S6 — Cold start** (`perf`): lazy/deferred torch + heavy deps in `main.py`/import graph; keep behavior identical. Depends on: none.
7. **S7 — Test infra** (`test`): session-scoped migrated DB + shared app fixture to cut per-test setup; keeps per-test data isolation guarantee. Depends on: none.

All slices are PROPOSAL ONLY — evidence first; each needs its own spec/design/tasks/apply/verify cycle.

---

## 12. Skill resolution + next recommended

- **Skill resolution**: `paths-injected` — loaded `sdd-explore` (orchestrator-injected), `code-optimization`, and `market-data-pipeline` (loaded but judged non-applicable: the data-access patterns here are snapshot reads via batched keyset pagination, not tick/OHLCV processing; its conventions were not used). Plus `_shared/sdd-phase-common.md` (Sections A-D) and `openspec-convention.md`.
- **Next recommended**: `sdd-propose` for `fase-16-performance`, using Section 10 scope + Section 11 slices as input. Confirmed: exploration only — nothing implemented, modified, committed, or PR'd.