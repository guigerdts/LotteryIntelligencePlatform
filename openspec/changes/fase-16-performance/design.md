# Design: Fase 16 — Performance

- Change: `fase-16-performance`
- Status: **designed**
- Store: **openspec**
- Date: 2026-08-18
- Sources: [exploration.md](./exploration.md) (baselines/hotspots) · [proposal.md](./proposal.md) (10 sub-slices, baseline→target §5, GF-1 §6, decisions §11) · [specs/](./specs/) (8 approved deltas: `backend`, `backtesting-engine`, `dl-engine`, `experiment-engine`, `ml-engine`, `performance`, `probability-engine`, `statistics-engine`) · precedent [fase-15-ai-assistant/design.md](../fase-15-ai-assistant/design.md) · DoD [IMPLEMENTATION_ROADMAP.md](../../../IMPLEMENTATION_ROADMAP.md)
- Owner mandate: conditions 1–12 bound every decision below (scope locked to proposal/spec; no implementation; MLE-xx resolution; S1b/S7 test-only; GF-1 hard gate; ProcessPool `max_workers=2` pure workers; S5a/S5b separate; S6 behavior-identical; S7 isolated; ≤400 lines/PR; no new deps/indexes/frontend; no tasks).

## 1. MLE-xx Mapping Resolution (owner condition 3)

**Decision: MLE-xx maps to the fase-7 delta spec — `openspec/changes/fase-7-machine-learning/specs/ml-engine/spec.md` — which is the authoritative carrier of the MLE-04/MLE-05 text.** That file exists on disk (verified) and contains the full `MLE-01..12` + `ME-01..05` requirement bodies, including the exact authoritative MLE-04 ("scikit-learn Only, Seeds Fixed") and MLE-05 ("Determinism & Quantization Contract") text that the fase-16 `ml-engine` delta spec MODIFIES.

Resolution rationale, evaluated options:
| Option | Verdict |
|---|---|
| **A — Map to the fase-7 delta spec (CHOSEN)** | The delta spec for fase-16 explicitly references it ("the ML engine main spec is archived under `fase-7-machine-learning/specs/ml-engine/`"). It is on disk, immutable, and carries the exact requirement text. No new file needed. |
| B — Create `openspec/specs/ml-engine/spec.md` now | Out of scope: capability specs are created at `sdd-archive` time, not during design; creating it now would modify openspec main beyond this change. |
| C — Documented alias without file anchor | Weaker provenance; condition 3 requires the exact authoritative file. |

**Effects**: verification for this change reads MLE-04/MLE-05 from the fase-7 delta file, not from a main `openspec/specs/ml-engine/` (which does not exist). When `fase-7` archives, the alias resolves automatically to `openspec/specs/ml-engine/spec.md`. This decision is recorded here (design.md) only — the specs themselves are NOT modified (owner condition: do not touch `specs/`).

## 2. Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| **MLE-xx mapping** | Map to fase-7 delta spec (see §1) | create main spec now / bare alias | authoritative text on disk; no out-of-scope openspec writes |
| **S1a reader** | `frequencies` → `select(StatFrequency).where(snapshot_id==...)` → `{int(number): int(count)}`; drop the `models.stat_value` import | fix the nonexistent model / map `metric_id` filter | `stat_frequency` is the real payload (PM-04); table has no `metric_id` column |
| **S1b scope** | Update `test_migrations.py` expectations to true head 0015 (add 0011 opt, 0012 bt, 0013 exp, 0014 meta, 0015 gen domains) + pin `tests/bt/test_migration.py` downgrade to `0012`/`0011` revisions | hide/skip tests | never mask drift; grep-verified only these 2 files pin head |
| **S2a N+1** | `_fetch_draws` → `select(DrawModel).options(selectinload(DrawModel.numbers))`; map numbers identically | raw SQL join | proven pattern in `draw_repository.list_draws:67-87`; same rows, one round-trip |
| **S2a LIMIT** | append `.limit(last)` when `last > 0` on `read_frequencies`/`read_gaps`, `ORDER BY number` kept | fetch-all-then-slice | STE-10; order preserved (deterministic) |
| **S2b run_ids** | nullable `run_ids` (Text) + non-unique index `ix_exp_comparisons_run_ids`, migration 0016, backfill in Python (chunked), legacy JSON-scan fallback while NULL rows exist, `compare()` writes `run_ids` on insert | SQL `json_each` backfill | Python backfill reuses the exact lookup derivation → no drift; JSON stays source of truth |
| **S3 worker interface** | module-level `_evaluate_window(window, strategy_id, config, lottery_id, number_pool, pick_count)` returning `(window_index, strategy_metrics, uniform_metrics, hyper_metrics)`; **per-window deterministic sub-seed** `random.Random(config.seed + window_index)` built inside the worker; strategy reconstructed from a module-level picklable static strategy | reuse a single shared benchmark instance across windows | shared-RNG reuse breaks under parallelism (RNG stream position differs per worker); per-window derived seeds are deterministic + injective and make serial==parallel; dataclass/plain-data payloads keep workers picklable and pure (PFM-04) |
| **S3 strategy picklability** | move the function-local `_Dummy` in `bt_service._make_strategy` to a module-level `StaticStrategy` in `backtesting/strategy.py` (implements `StrategyProtocol`, returns `[1,2,3,4,5]`) | pickle the closure | local classes are not picklable → pool crash; module-level class is picklable and behavior-identical |
| **S4 worker interface** | module-level `_fit_number(X_train, X_eval, y_train, y_eval, estimator_class_name, params)` → `(number, {metric: Decimal}, model)`; pool `max_workers=2`, results keyed by **sorted number**; family loop in `MlService.train` stays serial (D2) | parallelize family loop too | atomic per-family tx + no DB in workers; sorted-number freeze preserves determinism (PFM-01/04) |
| **S4 determinism absorber** | parity gate compares **quantized** `TrainResult` (checksum, fingerprint, quantized metrics), not raw floats | raw-float equality | quantization to `Numeric(20,8)` absorbs cross-process float noise; MLE-05 already mandates quantized digests |
| **S5a cache primitive** | new `core/response_cache.py`: `ThreadSafeLRU(maxsize=256)` = `OrderedDict` + `threading.RLock`; key `(snapshot_id, endpoint, *params)`; returns stored payload as-is (read-only contract) | `functools.lru_cache` / Redis / write-through | explicit key + bounded size + lock for FastAPI sync (threadpool) and async paths; no external store (PFM-05/D3); LRU bounds memory on the 2.4 GB box |
| **S5a keying nuance** | bounded-param reads fold `last` into the key (`(snapshot_id, endpoint, last)`) | `(snapshot_id, endpoint)` only | `read_frequencies(last=10)` vs `last=0` return different rows; PFM-05 canonical member is `(snapshot_id, endpoint)`; no collision, spec scenario preserved |
| **S5b ETag** | strong ETag `"<checksum>"` from the snapshot checksum/fingerprint; fallback weak `W/"<snapshot_id>:<version>"` when no hash field; `If-None-Match` match → `304` empty body, no recompute (REQ-13) | weak-only / middleware | checksum is content-derived → strong is correct under immutability; per-endpoint helper keeps 200 envelope untouched |
| **S6 lazy seam** | move `import torch` into `configure_deterministic_torch` + `train()`/`encode_weights()`; defer `dl/lstm.py`+`dl/mlp.py` imports into `_build_model`; move `from sklearn.metrics import ...` into `ml/engine.train`; move sklearn estimator imports out of `ml/registry` module top into `build_ml_registry` (first call) | keep eager / module-level sys.modules stub | verified: `import backend.app.main` loads 850 heavy modules (0 torch) ≈30 s on this box — sklearn via `api/v1/ml.py → ml_service → ml/engine → ml/registry` dominates; deferral set matches spec DLE-17/PFM-06; import-time side effects already live in `configure_deterministic_torch` (call-time), preserved |
| **S7 isolation** | session-scoped `migrated_db` file (alembic upgrade once) + session-scoped engine + per-test shared-connection transaction with SAVEPOINT join (`join_transaction_mode="create_savepoint"`), teardown `connection.rollback()`; `client` override binds the same connection | per-test data reset (DELETE seeded tables) | SAVEPOINT/rollback is proposal §11 D5; a test's own `commit()` releases only its savepoint → nothing leaks even with explicit commits; guard test proves it. SQLite shared connection needs `connect_args={"check_same_thread": False}` (sync `TestClient` is single-threaded, so no true concurrency). Fallback if SAVEPOINT join is incompatible: per-test reset of seeded tables. |

## 3. Architecture per Slice

### S1a — Probability StatValue fix (P0 correctness)
- **Files**: `backend/src/backend/app/services/probability_service.py` (lines 107-125 `_StatsReaderAdapter.frequencies`); `backend/tests/probability/test_probability_service.py`.
- **Design**: delete `from backend.app.models.stat_value import StatValue` (line 110); rewrite `frequencies(snapshot_id)` to `select(StatFrequency.number, StatFrequency.count).where(StatFrequency.snapshot_id == snapshot_id)` and return `{int(n): int(c)}`. No `metric_id` filter (table has none). Other `_StatsReaderAdapter` methods untouched.
- **Spec**: PM-04 scenarios 1-3 (frequency-derived rate, generate succeeds with active snapshot, stat_frequency payload read).
- **Measurement gate**: n/a (correctness) — regression test + `backend/.venv/bin/pytest tests/probability`.
- **GF-1**: none (no engine math change).
- **Risks/rollback**: field-shape mismatch → caught by regression test; revert commit.

### S1b — Migration-contract refresh (P0 suite health; test-only per owner condition 4)
- **Files**: `backend/tests/test_migrations.py`; `backend/tests/bt/test_migration.py`.
- **Design**: extend table/index expectation sets with the 0011 opt, 0012 bt, 0013 exp, 0014 meta, 0015 gen domains; replace stale head-pin sets with the true 0015 set; in `test_migration.py` pin `command.downgrade(cfg, "0012")` / `"0011"` instead of `"-1"`/`head`. **No production or migration code changes** — this is a task unit, not a new capability spec.
- **Spec**: n/a (test-infra unit; unblocks S2b migration chain 0016 `down_revision=0015`).
- **Measurement gate**: `test_migrations.py` 14/14 + `tests/bt/test_migration.py` 7/7 pass, none skipped.
- **Risks/rollback**: wrong expectations encode drift → grep-verified only these two files pin head; revert commit.

### S2a — bt N+1 + statistics LIMIT pushdown
- **Files**: `backend/src/backend/app/services/bt_service.py` (`_fetch_draws`, 198-220); `backend/src/backend/app/services/statistics_service.py` (`read_frequencies`/`read_gaps`, 135-158); `backend/tests/bt/` + `backend/tests/statistics/`.
- **Design**: `_fetch_draws` → `select(DrawModel).options(selectinload(DrawModel.numbers))`, keep `order_by(draw_date)`, map `numbers`/`super_number` identically; `read_frequencies`/`read_gaps` append `.limit(last)` when `last > 0`, keep `ORDER BY number`.
- **Spec**: BTS-04 (draw load ≤2 SELECTs, mapped rows identical); STE-10 (bounded read, order preserved, no-limit unchanged).
- **Measurement gate**: assert-queries test (≤2 draw SELECTs); `backend/.venv/bin/pytest tests/bt -q -k run_returns_200 --durations=1` ≤5.0 s (baseline 6.35).
- **GF-1**: none (same rows; LIMIT keeps order).
- **Risks/rollback**: order change from LIMIT → covered by STE-10 scenario; revert commit. Depends: S1a.

### S2b — exp_comparisons indexed run_ids + migration 0016
- **Files**: `backend/src/backend/app/models/exp_comparison.py`; new `backend/alembic/versions/0016_exp_comparisons_run_ids.py`; `backend/src/backend/app/services/exp_service.py`; `backend/tests/exp/` + `backend/tests/test_migrations.py`.
- **Design**:
  - Model: add `run_ids: Mapped[str | None] = mapped_column(Text, nullable=True)` (indexes are owned by migrations per repo pattern).
  - Migration 0016: `revision="0016_exp_comparisons_run_ids"`, `down_revision="0015_gen_tables"`; `op.add_column` (nullable), `op.create_index("ix_exp_comparisons_run_ids", "exp_comparisons", ["run_ids"])`; **Python backfill** chunked (500-row batches) reusing the shared derivation `run_ids = ",".join(str(i) for i in sorted(r["run_id"] for r in json.loads(row.comparison_json)["runs"]))`; downgrade drops index + column only.
  - Service: module-level `_run_ids_key(sorted_run_ids)` helper (single source of derivation); `_find_cached_comparison` → single `WHERE experiment_id == ? AND run_ids == ?` indexed lookup; **legacy fallback**: if no indexed match AND the experiment still has `run_ids IS NULL` rows, run the verbatim pre-change JSON-scan; `compare()` insert path (395-398) sets `run_ids=_run_ids_key(sorted_ids)`.
- **Spec**: EXP-009 scenarios 1-4 (single indexed lookup, NULL fallback, 0016 up/down round-trip, compare target); EXP-005 (idempotent comparison, no blob parse on lookup).
- **Measurement gate**: `backend/.venv/bin/pytest tests/exp -q -k compare --durations=1`; migration 0016 up/down round-trip test green.
- **GF-1**: none (lookup path only; JSON blob untouched).
- **Risks/rollback**: backfill cost on large tables → nullable + chunked + legacy fallback; `alembic downgrade 0015` + revert service. Depends: S1b.

### S3 — Backtest window parallelization
- **Files**: `backend/src/backend/app/backtesting/engine.py` (window loop 94-130); `backend/src/backend/app/backtesting/strategy.py` (module-level `StaticStrategy`); `backend/src/backend/app/services/bt_service.py` (`_make_strategy` → module-level builder); new `backend/tests/bt/test_parallel_parity.py`.
- **Design**: extract module-level `_evaluate_window(window, strategy_id, config, lottery_id, number_pool, pick_count)` → builds `DrawContext`s, `StaticStrategy`, and **per-window** `UniformRandomBenchmark(pool, pick, config.seed + window.index)` / `HypergeometricBenchmark(...)`; computes the 3 metric sets; returns `(window_index, strategy_metrics, uniform_metrics, hypergeometric_metrics)`. `BacktestEngine.run(..., parallel: bool = False)`: serial path = `for w in windows` calling `_evaluate_window` (existing callers unchanged); parallel path = `concurrent.futures.ProcessPoolExecutor(max_workers=2).map(...)` (map preserves input order → `window_index` order by construction); pool used only when `len(windows) >= 2`, else serial (small-window overhead). Aggregate + fingerprint unchanged (fingerprint computed before windows from config/data). `BtService.run` passes `parallel=True`; engine keeps `parallel=False` default.
- **Spec**: BTE-05 (reproducibility, seed affects results, serial-vs-parallel parity byte-identical, deterministic ordering by window_index); BTS-04 (target ≤3.5 s after S3); PFM-01/PFM-04 (byte-identical gate, bounded pool, pure workers).
- **Measurement gate**: `backend/.venv/bin/pytest tests/bt -q -k run_returns_200 --durations=1` ≤3.5 s (baseline 6.35).
- **GF-1**: new parity test serial vs parallel (fingerprint, `aggregate_metrics`, `window_history` byte-identical) + existing `tests/bt/test_determinism.py` + root `tests/test_determinism.py` all green — any byte difference **blocks the slice**.
- **Risks/rollback**: benchmark/strategy picklability (solved via module-level classes + plain data payloads); process overhead on few small windows (solved via serial fallback on 1 window); pool spawn cost → measurement gate decides. Revert `engine.py`. Depends: S2a.

### S4 — ML per-number parallelization
- **Files**: `backend/src/backend/app/ml/engine.py` (per-number loop 124-135); new `backend/tests/ml/test_ml_parallel_parity.py`.
- **Design**: module-level `_fit_number(X_train, X_eval, y_train, y_eval, estimator_name, params, number)` → `(number, {metric: Decimal}, fitted_model)`, metrics computed in-worker (accuracy/precision/recall/f1/roc_auc, quantized). `MlEngine.train(..., parallel: bool = False)`: serial = current loop; parallel = `ProcessPoolExecutor(max_workers=2).map` over `all_numbers` (sorted), results keyed by number; parent reconstructs `per_number`, `models`, `metrics`, fingerprint, checksum identically. **Family loop in `MlService.train` stays serial** (D2, MLE-04 scenario). `random_state=0` per worker (registry) — no shuffle.
- **Spec**: MLE-04 (seeded training, allowlist, parallel fits bounded and pure, family loop serial); MLE-05 (rerun matches, float excluded from checksum, serial-vs-parallel parity byte-identical, targets ≤4.5 s / ≤3.0 s); PFM-01/04.
- **Measurement gate**: `backend/.venv/bin/pytest tests/ml -q -k test_train_basic --durations=1` ≤4.5 s (baseline 8.18); `... -k test_engine_train_basic --durations=1` ≤3.0 s (baseline 5.37).
- **GF-1**: new parity test (checksum, fingerprint, quantized per-number metrics byte-identical serial vs parallel) + `tests/ml/test_ml_determinism_e2e.py` + root `tests/test_determinism.py` — any byte difference **blocks the slice**.
- **Risks/rollback**: pickle cost of 49 fitted models back (bounded by `max_workers=2`; final parent memory equals serial baseline; transient worker copies only); BLAS thread oversubscription (2 workers × default threads on 3 cores) → if a family shows cross-process quantized drift, per-family serial fallback + parity gate decides. Revert `engine.py`.

### S5a — Snapshot read cache (immutable, version-keyed)
- **Files**: new `backend/src/backend/app/core/response_cache.py`; `statistics_service.py`, `probability_service.py`, `graph_service.py`, `ml_service.py`, `bt_service.py` read paths.
- **Design**: `ThreadSafeLRU(maxsize=256)` (`OrderedDict` + `threading.RLock`; `get`/`set` atomic; eviction on insert past maxsize). Service read boundaries wrap their immutable payload build with key `(snapshot_id, endpoint, *params)` (e.g. `(snap.id, "statistics.frequencies", last)`). No write-through: a new snapshot id = new key (immutability → trivial invalidation). Wired reads: `read_frequencies`, `read_gaps`, `read_averages`, `read_scalars`, probability `read_values`, ml `get_metrics`, graph read, bt `results`. Returned payloads are treated read-only (routes serialize, never mutate).
- **Spec**: PFM-05 (cache hit byte-identical, version bump invalidates by key, no external store); REQ-11 preserved (reads never recompute).
- **Measurement gate**: `backend/.venv/bin/pytest tests/statistics -q --durations=1` + cache tests (hit/miss, golden byte-identical cached vs fresh).
- **GF-1**: golden test — cached payload == fresh DB-built payload byte-identical; determinism suite re-run after wiring.
- **Risks/rollback**: key collision (solved: version-keyed + param folding); memory growth (bounded LRU ≤256 entries × ≤2 MB worst case, well under 2.4 GB available). Delete module / revert wiring. Depends: S1a.

### S5b — ETag/304 on read endpoints + cache tests
- **Files**: `backend/src/backend/app/api/v1/statistics.py` + prob/graph/ml/bt read routers; new `backend/tests/api/test_etag.py`.
- **Design**: helper `etag_for(snapshot) -> str` = strong `"<checksum>"` (statistics `checksum`; ml `checksum`/`input_fingerprint`; bt `fingerprint`) else weak `W/"<snapshot_id>:<version>"`; `should_not_modify(request, etag)` compares `If-None-Match`. Applied to read endpoints (statistics frequencies/gaps/averages/scalars, probability values, graph read, ml metrics, bt results) with `Response` param; match → `304` empty body; otherwise 200 with the unchanged envelope + `ETag` header.
- **Spec**: REQ-13 scenarios 1-4 (304 no body, cache hit byte-identical, version bump new ETag, never recompute); PFM-05.
- **Measurement gate**: `backend/.venv/bin/pytest tests/api -q` + ETag tests (round-trip, 304, version bump).
- **GF-1**: golden — 200 response byte-identical with/without ETag; no recompute path.
- **Risks/rollback**: header correctness with envelope → covered by tests; revert API wiring. Depends: S5a.

### S6 — Lazy torch / heavy-dep import
- **Files**: `backend/src/backend/app/dl/determinism.py`, `dl/engine.py`, `dl/lstm.py`, `dl/mlp.py`, `dl/weights.py`; `backend/src/backend/app/ml/engine.py`, `ml/registry.py`; new `backend/tests/test_cold_start.py`.
- **Design**: move `import torch` from module top into `configure_deterministic_torch` (determinism.py) and into `train()` (engine.py); move `import torch` into `encode_weights`; move `from dl.lstm import LotteryLSTM` / `dl.mlp import LotteryMLP` into `_build_model` (first-use per family); move `from sklearn.metrics import ...` into `MlEngine.train`; move sklearn estimator imports in `registry.py` into `build_ml_registry` (first call). `from __future__ import annotations` already defers the type annotations that reference torch. No computation change.
- **Spec**: DLE-17 (deferred import preserves behavior, DL determinism preserved, cold-start ≤8 s); PFM-06 (target + deferred import still works on first use).
- **Measurement gate**: `time python -c "import backend.app.main"` ≤8 s (baseline 25.3 s, re-measured 30-40 s on this loaded box; sklearn is the dominant eager cost — torch already 0 modules via `main`). Automated gate: `tests/test_cold_start.py` asserts `"torch" not in sys.modules` and `"sklearn" not in sys.modules` after a fresh `import backend.app.main`; DL determinism tests stay green.
- **GF-1**: none (no computation change) — DL determinism suite is the behavior gate.
- **Risks/rollback**: accidental eager import reintroduces cost → module-presence test is the guard; import-time side effects must move with the import (verified: `configure_deterministic_torch` applies thread/seed config at call time); behavior drift → DL determinism e2e. Revert.

### S7 — Test infrastructure (TEST-ENV only; isolated per owner condition 9)
- **Files**: `backend/tests/conftest.py`; `backend/tests/api/conftest.py`; new `backend/tests/test_isolation_guard.py`.
- **Design**: `migrated_db` → session-scoped (alembic upgrade once to a session tmp file); `api_engine`/`session_factory` → session-scoped; a session-scoped `connection` fixture (one connection, `connect_args={"check_same_thread": False}`); per-test `db` fixture = `sessionmaker(bind=connection, join_transaction_mode="create_savepoint")` session, teardown `connection.rollback()` — a test's `commit()` releases only its savepoint, so seeded rows never leak. `client` override binds the SAME connection/savepoint so requests see seeded rows. Guard test: test A seeds + commits; test B asserts the table is empty (no leakage). Document the ~1 GB-memory full-suite limitation as a known TEST-ENV constraint (not fixed in production code).
- **Spec**: n/a (test-infra task unit — not a new capability spec; per proposal §3 S7 + owner condition 4).
- **Measurement gate**: `backend/.venv/bin/pytest tests/api -q --durations=10` setup ≤0.3 s/test (baseline ~3 s); app-backed dirs (statistics/api/gen/bt) full pass; isolation guard green.
- **Risks/rollback**: isolation regression across app-backed dirs (highest-risk TEST-ENV change) → guard test + full-dir runs; SQLite shared-connection thread-safety → `check_same_thread=False` + sync TestClient (single-threaded); SAVEPOINT-incompatible fixtures → documented fallback (per-test data reset). Revert `conftest`.

## 4. Dependency Graph (DAG)

```
S1a (correctness) ──→ S2a ──→ S3          S5a ──→ S5b
                        │
S1b (suite health) ──→ S2b
S4 ── independent
S6 ── independent
S7 ── independent
```
- S5 (S5a→S5b) depends on S1a (probability read correctness first). S4/S6/S7 independent. No other edges.

## 5. Technical Risks & Mitigations

| Risk | Slice | Mitigation |
|---|---|---|
| Pickle cost/volume for 49 fitted models | S4 | `max_workers=2` bounds transient copies; parent memory equals serial baseline; `TrainResult.models` contract preserved; parity gate on quantized payload |
| Process overhead on small windows | S3 | serial fallback when `len(windows) < 2`; map preserves order; measurement gate ≤3.5 s decides viability |
| Benchmark RNG divergence serial vs parallel | S3 | per-window deterministic sub-seed `config.seed + window_index` built in-worker; parity test is the hard gate |
| Cache memory growth on 2.4 GB box | S5a | bounded `ThreadSafeLRU(maxsize=256)`; payloads ≤2 MB worst case; key folding prevents cross-param bloat |
| Lazy-import behavior drift | S6 | import-time side effects audited (torch thread/seed config already call-time); DL determinism e2e + `test_cold_start` module-presence guard |
| Migration backfill on large `exp_comparisons` | S2b | nullable column + chunked Python backfill (500-row batches) + legacy JSON-scan fallback while NULL rows exist |
| S7 isolation regression | S7 | SAVEPOINT join rollback + guard test + app-backed dirs full pass; fallback = per-test data reset |
| BLAS thread oversubscription under 2 workers | S4 | per-family serial fallback on quantized parity failure; gate decides, never silent |

## 6. Line Forecast per Slice (≤400 binding, PFM-03)

Measured at apply with `git diff --numstat` additions+deletions; goldens excluded (phase-common §E). Design-time check: none of the design refinements push any slice over 400 → **no split required at design time**; if the authored diff exceeds 400 at apply, the slice splits into chained PRs (owner condition 10, no `size:exception`).

| Slice | Est. authored lines (code + tests) | ≤400 | Split decision |
|---|---|---|---|
| S1a | ~75 | Yes | single |
| S1b | ~160 | Yes | single |
| S2a | ~95 | Yes | single |
| S2b | ~180 | Yes | single |
| S3 | ~140 | Yes | single |
| S4 | ~140 | Yes | single |
| S5a | ~155 | Yes | single |
| S5b | ~140 | Yes | single |
| S6 | ~70 | Yes | single |
| S7 | ~140 | Yes | single |
| **Total** | **~1 295** | — | 10 PRs |

## 7. Test Plan per Slice

| Slice | Test files | Tests |
|---|---|---|
| S1a | `tests/probability/test_probability_service.py` | regression: seed lottery + draws + active stats snapshot (`stat_frequency` rows) → `generate` returns rows (no crash); reader maps `{number: count}` |
| S1b | `tests/test_migrations.py`, `tests/bt/test_migration.py` | head=0015 table/index expectations; downgrade pinned to 0012/0011; none skipped |
| S2a | `tests/bt/test_assert_queries.py` (new), `tests/statistics/` | assert-queries: draw load ≤2 SELECTs; mapped rows identical; `last` LIMIT keeps `ORDER BY number`; no-limit unchanged |
| S2b | `tests/exp/` + `tests/test_migrations.py` | 0016 up/down round-trip + backfill; single indexed lookup (assert no blob `json.loads` on hit path); NULL-run_ids legacy fallback; `compare()` writes `run_ids` |
| S3 | `tests/bt/test_parallel_parity.py` (new) + existing `test_determinism.py` | serial-vs-parallel byte-identical (fingerprint, aggregate, window_history); `window_index` ordering; existing determinism gates unchanged |
| S4 | `tests/ml/test_ml_parallel_parity.py` (new) + existing `test_ml_determinism_e2e.py` | serial-vs-parallel byte-identical (checksum, fingerprint, quantized metrics); sorted-number keying; existing e2e gates unchanged |
| S5a | `tests/test_response_cache.py` (new) | hit/miss keying incl. `last` folding; eviction; thread-safety (concurrent reads); golden cached == fresh byte-identical; version bump → new key |
| S5b | `tests/api/test_etag.py` (new) | ETag derivation; `If-None-Match` → 304 empty body; version bump → new ETag (never stale 304); 200 envelope byte-identical with/without ETag; no recompute |
| S6 | `tests/test_cold_start.py` (new) + `tests/dl/test_determinism.py`, `tests/dl/test_dl_determinism_e2e.py` | module-presence assert (no torch/sklearn after `import backend.app.main`); DL determinism after deferral; torch/sklearn importable + functional at first use |
| S7 | `tests/test_isolation_guard.py` (new) + app-backed dirs | guard: test A seeds+commits, test B sees empty tables; setup ≤0.3 s/test; statistics/api/gen/bt full pass |

## 8. Rollback Plan per Slice

| Slice | Rollback |
|---|---|
| S1a | revert commit (reader rewrite) |
| S1b | revert commit (test expectations) |
| S2a | revert commit (service SQL) |
| S2b | `alembic downgrade 0015` (drops column + index) + revert model/service |
| S3 | revert `engine.py` (+ strategy module) — service `parallel=True` flips back to serial default |
| S4 | revert `engine.py` — `parallel=False` default restores serial loop |
| S5a | delete `core/response_cache.py` + revert service wiring |
| S5b | revert API ETag wiring |
| S6 | revert import moves |
| S7 | revert `conftest.py` (function-scoped fixtures restored) |

## 9. Threat Matrix

Process-pool slices (S3/S4) introduce a **process boundary** but no shell/subprocess-command, routing, VCS/PR-automation, or executable-classification boundary. `ProcessPoolExecutor` invokes fixed module-level callables only — worker functions are never derived from user input. Matrix rows:

| Boundary | Applicability |
|---|---|
| Documentation-like paths | N/A — no executable-file handling introduced |
| Git repository selection | N/A — no git path selectors |
| Commit state | N/A — no index/worktree automation |
| Push state | N/A — no push logic |
| PR commands | N/A — no PR command composition |

Expected safe/failure behavior for the one applicable boundary (process): safe = picklable plain-data payloads, bounded pool (2), no DB sessions in workers (PFM-04); failure = unpicklable payload or worker exception → `BtRunError`/failed header (MLE-08 failed-snapshot path), parity/determinism gates catch divergence. RED tests: pickling round-trip of the worker payload (part of parity tests) and "no DB session in worker" asserted via the module-level worker never importing session/engine (structural assert in parity test).

## 10. Next Recommended

`sdd-tasks` for `fase-16-performance` — pending owner gate on this design (all proposal §11 decisions D1-D5 confirmed; no open design questions blocking).